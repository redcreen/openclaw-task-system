import AppKit
import Foundation

private enum AppConstants {
    static let refreshInterval: TimeInterval = 60
    static let commandTimeout: TimeInterval = 25
    static let menuBarLabelPrefix = "Codex"
}

private struct StatusEnvelope: Decodable {
    let usage: UsageSummary?
}

private struct UsageSummary: Decodable {
    let updatedAt: Double?
    let providers: [ProviderUsage]
}

private struct ProviderUsage: Decodable {
    let provider: String
    let displayName: String
    let windows: [UsageWindow]
    let plan: String?
    let error: String?
}

private struct UsageWindow: Decodable {
    let label: String
    let usedPercent: Double
    let resetAt: Double?
}

private struct SnapshotResult {
    let summary: UsageSummary
    let fetchedAt: Date
}

private enum QuotaError: LocalizedError {
    case invalidOutput(String)
    case commandFailed(String)
    case missingCodexProvider

    var errorDescription: String? {
        switch self {
        case .invalidOutput(let detail):
            return "无法解析 openclaw 输出：\(detail)"
        case .commandFailed(let detail):
            return "openclaw status 执行失败：\(detail)"
        case .missingCodexProvider:
            return "当前 usage 快照里没有找到 Codex provider。"
        }
    }
}

private final class QuotaFetcher {
    private let decoder = JSONDecoder()
    private let commandPath: String
    private let workspaceURL: URL

    init(
        commandPath: String = ProcessInfo.processInfo.environment["CODEX_QUOTA_OPENCLAW_PATH"]
            ?? "openclaw",
        workspaceURL: URL = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(".openclaw")
    ) {
        self.commandPath = commandPath
        self.workspaceURL = workspaceURL
    }

    func fetch() async throws -> SnapshotResult {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: commandPath)
        process.arguments = ["status", "--usage", "--json", "--timeout", "20000"]
        process.currentDirectoryURL = workspaceURL

        var env = ProcessInfo.processInfo.environment
        env["NO_COLOR"] = "1"
        process.environment = env

        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr

        try process.run()

        let timeoutTask = Task {
            try await Task.sleep(nanoseconds: UInt64(AppConstants.commandTimeout * 1_000_000_000))
            if process.isRunning {
                process.terminate()
            }
        }

        process.waitUntilExit()
        timeoutTask.cancel()

        let stdoutData = stdout.fileHandleForReading.readDataToEndOfFile()
        let stderrData = stderr.fileHandleForReading.readDataToEndOfFile()
        let stdoutText = String(decoding: stdoutData, as: UTF8.self)
        let stderrText = String(decoding: stderrData, as: UTF8.self)

        guard process.terminationStatus == 0 else {
            let detail = [stderrText, stdoutText]
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .first(where: { !$0.isEmpty }) ?? "exit code \(process.terminationStatus)"
            throw QuotaError.commandFailed(detail)
        }

        let jsonText = try extractJSONObject(from: stdoutText)
        let summary = try decodeUsageSummary(from: jsonText)
        return SnapshotResult(summary: summary, fetchedAt: Date())
    }

    private func decodeUsageSummary(from jsonText: String) throws -> UsageSummary {
        let jsonData = Data(jsonText.utf8)
        if let envelope = try? decoder.decode(StatusEnvelope.self, from: jsonData),
           let usage = envelope.usage {
            return usage
        }
        if let usage = try? decoder.decode(UsageSummary.self, from: jsonData) {
            return usage
        }
        throw QuotaError.invalidOutput("JSON 不包含 usage.providers")
    }

    private func extractJSONObject(from text: String) throws -> String {
        guard let startIndex = text.firstIndex(of: "{") else {
            throw QuotaError.invalidOutput("stdout 里没有 JSON")
        }

        var depth = 0
        var inString = false
        var isEscaped = false
        var endIndex: String.Index?

        for index in text[startIndex...].indices {
            let character = text[index]

            if inString {
                if isEscaped {
                    isEscaped = false
                } else if character == "\\" {
                    isEscaped = true
                } else if character == "\"" {
                    inString = false
                }
                continue
            }

            if character == "\"" {
                inString = true
                continue
            }

            if character == "{" {
                depth += 1
            } else if character == "}" {
                depth -= 1
                if depth == 0 {
                    endIndex = text.index(after: index)
                    break
                }
            }
        }

        guard let endIndex else {
            throw QuotaError.invalidOutput("JSON 片段不完整")
        }

        return String(text[startIndex..<endIndex])
    }
}

@MainActor
private final class StatusController: NSObject {
    private let fetcher = QuotaFetcher()
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let menu = NSMenu()
    private let titleItem = NSMenuItem(title: "Codex Quota Bar", action: nil, keyEquivalent: "")
    private let subtitleItem = NSMenuItem(title: "正在初始化…", action: nil, keyEquivalent: "")
    private let refreshItem = NSMenuItem(title: "立即刷新", action: #selector(refreshFromMenu), keyEquivalent: "r")
    private let quitItem = NSMenuItem(title: "退出", action: #selector(quitApp), keyEquivalent: "q")

    private var timer: Timer?
    private var latestSnapshot: SnapshotResult?
    private var latestError: String?
    private var isRefreshing = false

    func start() {
        statusItem.button?.title = "\(AppConstants.menuBarLabelPrefix) --"

        titleItem.isEnabled = false
        subtitleItem.isEnabled = false
        refreshItem.target = self
        quitItem.target = self

        menu.autoenablesItems = false
        statusItem.menu = menu

        rebuildMenu()
        refresh()

        timer = Timer.scheduledTimer(withTimeInterval: AppConstants.refreshInterval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.refresh()
            }
        }
    }

    @objc
    private func refreshFromMenu() {
        refresh(force: true)
    }

    @objc
    private func quitApp() {
        NSApp.terminate(nil)
    }

    private func refresh(force: Bool = false) {
        if isRefreshing && !force {
            return
        }

        isRefreshing = true
        subtitleItem.title = "正在刷新…"
        statusItem.button?.title = latestSnapshot.flatMap { Self.menuBarTitle(from: $0.summary) } ?? "\(AppConstants.menuBarLabelPrefix) ..."
        rebuildMenu()

        let fetcher = self.fetcher
        Task {
            do {
                let snapshot = try await fetcher.fetch()
                await self.applySnapshot(snapshot)
            } catch {
                await self.applyRefreshError(error.localizedDescription)
            }
        }
    }

    private func applySnapshot(_ snapshot: SnapshotResult) {
        latestSnapshot = snapshot
        latestError = nil
        isRefreshing = false
        statusItem.button?.title = Self.menuBarTitle(from: snapshot.summary)
        rebuildMenu()
    }

    private func applyRefreshError(_ message: String) {
        latestError = message
        isRefreshing = false
        statusItem.button?.title = "\(AppConstants.menuBarLabelPrefix) !"
        rebuildMenu()
    }

    private func rebuildMenu() {
        menu.removeAllItems()
        menu.addItem(titleItem)
        subtitleItem.title = subtitleText()
        menu.addItem(subtitleItem)
        menu.addItem(.separator())

        if let snapshot = latestSnapshot {
            let providers = snapshot.summary.providers.sorted { lhs, rhs in
                if lhs.provider == "openai-codex" { return true }
                if rhs.provider == "openai-codex" { return false }
                return lhs.displayName.localizedCaseInsensitiveCompare(rhs.displayName) == .orderedAscending
            }

            for provider in providers {
                let providerItem = NSMenuItem(title: providerLine(provider), action: nil, keyEquivalent: "")
                providerItem.isEnabled = false
                menu.addItem(providerItem)

                if let error = provider.error {
                    let errorItem = NSMenuItem(title: "  \(error)", action: nil, keyEquivalent: "")
                    errorItem.isEnabled = false
                    menu.addItem(errorItem)
                    continue
                }

                for window in provider.windows {
                    let item = NSMenuItem(title: "  \(windowLine(window))", action: nil, keyEquivalent: "")
                    item.isEnabled = false
                    menu.addItem(item)
                }
            }

            menu.addItem(.separator())
        }

        if let latestError {
            let errorItem = NSMenuItem(title: "错误: \(latestError)", action: nil, keyEquivalent: "")
            errorItem.isEnabled = false
            menu.addItem(errorItem)
            menu.addItem(.separator())
        }

        menu.addItem(refreshItem)
        menu.addItem(quitItem)
    }

    private func subtitleText() -> String {
        if isRefreshing {
            return "正在刷新…"
        }
        if let latestSnapshot {
            let formatter = RelativeDateTimeFormatter()
            formatter.unitsStyle = .short
            return "上次刷新 \(formatter.localizedString(for: latestSnapshot.fetchedAt, relativeTo: Date()))"
        }
        if let latestError {
            return latestError
        }
        return "等待第一次刷新"
    }

    private func providerLine(_ provider: ProviderUsage) -> String {
        let planSuffix = provider.plan.map { " (\($0))" } ?? ""
        return "\(provider.displayName)\(planSuffix)"
    }

    private func windowLine(_ window: UsageWindow) -> String {
        let remaining = max(0, min(100, 100 - window.usedPercent))
        let resetSuffix = resetText(window.resetAt).map { " · 重置 \($0)" } ?? ""
        return "\(window.label): \(Int(remaining.rounded()))% 剩余\(resetSuffix)"
    }

    private func resetText(_ resetAt: Double?) -> String? {
        guard let resetAt else {
            return nil
        }
        let date = Date(timeIntervalSince1970: resetAt / 1000)
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .short
        return formatter.localizedString(for: date, relativeTo: Date())
    }

    private static func menuBarTitle(from summary: UsageSummary) -> String {
        if let codex = summary.providers.first(where: { $0.provider == "openai-codex" || $0.displayName == "Codex" }) {
            let remaining = codex.windows.map { 100 - $0.usedPercent }.min()
            if let remaining {
                return "\(AppConstants.menuBarLabelPrefix) \(Int(max(0, min(100, remaining)).rounded()))%"
            }
            if codex.error != nil {
                return "\(AppConstants.menuBarLabelPrefix) !"
            }
            return "\(AppConstants.menuBarLabelPrefix) --"
        }

        if let best = summary.providers.first,
           let remaining = best.windows.map({ 100 - $0.usedPercent }).min() {
            return "\(best.displayName) \(Int(max(0, min(100, remaining)).rounded()))%"
        }

        return "\(AppConstants.menuBarLabelPrefix) --"
    }
}

@MainActor
private final class AppDelegate: NSObject, NSApplicationDelegate {
    private let controller = StatusController()

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        controller.start()
    }
}

@main
struct CodexQuotaBar {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.run()
    }
}
