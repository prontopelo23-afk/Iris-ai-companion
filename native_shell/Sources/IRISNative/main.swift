import AppKit
import AVFoundation
import Foundation
import WebKit
import Darwin

enum Constants {
    static let appName = "IRIS"
    static let bundleID = "com.karmaswoop.iris"
    static let operatorName = "Swoop"
    static let backendBase = URL(string: "http://127.0.0.1:8876")!
    static let healthURL = backendBase.appendingPathComponent("api/health")
    static let readyURL = backendBase.appendingPathComponent("api/ready")
    static let cockpitURL = URL(string: "http://127.0.0.1:8876/?shell=native&operator=Swoop&nativeApp=1")!
    static let launchAgentLabel = "com.iris.v3.companion"
    static let launchAgentPath = "\(NSHomeDirectory())/Library/LaunchAgents/com.iris.v3.companion.plist"
    static let bootstrapLockPath = "\(NSTemporaryDirectory())com.karmaswoop.iris.bootstrap.lock"
    static let logDir = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Logs/IRIS", isDirectory: true)
    static let logFile = logDir.appendingPathComponent("launcher.log")
    static let launcherScript = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("AI-Local/iris_v3_companion/bin/iris-v11-open-native-app")
    static let companionRoot = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("AI-Local/iris_v3_companion", isDirectory: true)
    static let serverErrorLog = companionRoot.appendingPathComponent("logs/server.err.log")
    static let serverOutputLog = companionRoot.appendingPathComponent("logs/server.out.log")
    static let minWindowSize = NSSize(width: 1180, height: 760)
    static let windowSize = NSRect(x: 0, y: 0, width: 1440, height: 900)
}

final class LogSink: @unchecked Sendable {
    static let shared = LogSink()
    private let queue = DispatchQueue(label: "com.karmaswoop.iris.logs", qos: .utility)

    func write(_ message: String) {
        let line = "[\(timestamp())] \(message)\n"
        queue.async {
            do {
                try FileManager.default.createDirectory(at: Constants.logDir, withIntermediateDirectories: true)
                if !FileManager.default.fileExists(atPath: Constants.logFile.path) {
                    FileManager.default.createFile(atPath: Constants.logFile.path, contents: nil)
                }
                let handle = try FileHandle(forWritingTo: Constants.logFile)
                defer { try? handle.close() }
                try handle.seekToEnd()
                handle.write(Data(line.utf8))
            } catch {
                fputs(line, stderr)
            }
        }
    }

    private func timestamp() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return formatter.string(from: Date())
    }
}

struct HTTPResult {
    let statusCode: Int
    let data: Data
}

final class HTTPResultBox: @unchecked Sendable {
    var value: HTTPResult?
}

final class JSONPayloadBox: @unchecked Sendable {
    var value: [String: Any]?
}

final class ErrorBox: @unchecked Sendable {
    var value: Error?
}

enum BackendError: LocalizedError {
    case launchAgentMissing
    case shellCommandFailed(String)
    case notReady(String)

    var errorDescription: String? {
        switch self {
        case .launchAgentMissing:
            return "Le LaunchAgent IRIS est introuvable."
        case let .shellCommandFailed(message):
            return message
        case let .notReady(message):
            return message
        }
    }
}

enum BackendController {
    static func healthIsOK(timeout: TimeInterval = 1.4) -> Bool {
        guard let result = httpGet(Constants.healthURL, timeout: timeout) else { return false }
        return result.statusCode == 200
    }

    static func readyPayload(timeout: TimeInterval = 1.4) -> [String: Any]? {
        guard let result = httpGet(Constants.readyURL, timeout: timeout), result.statusCode == 200 else { return nil }
        guard let payload = try? JSONSerialization.jsonObject(with: result.data) as? [String: Any] else { return nil }
        return payload
    }

    static func waitUntilReady(timeout: TimeInterval, progress: (String) -> Void) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        let phases = [
            "system link // vérification du mesh local",
            "backend // attente du companion",
            "ready gate // synchronisation du cockpit",
            "handoff // projection de la chambre"
        ]
        var tick = 0
        while Date() < deadline {
            if let payload = readyPayload(), (payload["ready"] as? Bool) == true {
                return true
            }
            progress(phases[min(tick / 4, phases.count - 1)])
            Thread.sleep(forTimeInterval: 0.5)
            tick += 1
        }
        return false
    }

    static func startIfNeeded(forceRestart: Bool) throws {
        if !forceRestart && healthIsOK() {
            LogSink.shared.write("backend:health-ok")
            return
        }
        try withBootstrapLock {
            if !forceRestart && healthIsOK() {
                LogSink.shared.write("backend:health-ok-after-lock")
                return
            }
            if forceRestart {
                LogSink.shared.write("backend:kickstart-forced")
                try kickstart()
                return
            }
            if launchAgentLoaded() {
                LogSink.shared.write("backend:kickstart-existing-agent")
                try kickstart()
            } else {
                LogSink.shared.write("backend:bootstrap-missing-agent")
                try bootstrap()
                try kickstart()
            }
        }
    }

    static func openLogs() {
        let candidates = [Constants.logFile, Constants.serverErrorLog, Constants.serverOutputLog].filter {
            FileManager.default.fileExists(atPath: $0.path)
        }
        if candidates.isEmpty {
            NSWorkspace.shared.open(Constants.logDir)
            return
        }
        NSWorkspace.shared.activateFileViewerSelecting(candidates)
    }

    private static func bootstrap() throws {
        guard FileManager.default.fileExists(atPath: Constants.launchAgentPath) else {
            throw BackendError.launchAgentMissing
        }
        let uid = getuid()
        let domain = "gui/\(uid)"
        try runShell(["/bin/launchctl", "bootstrap", domain, Constants.launchAgentPath])
    }

    private static func kickstart() throws {
        let uid = getuid()
        try runShell(["/bin/launchctl", "kickstart", "-k", "gui/\(uid)/\(Constants.launchAgentLabel)"])
    }

    private static func launchAgentLoaded() -> Bool {
        let uid = getuid()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        process.arguments = ["print", "gui/\(uid)/\(Constants.launchAgentLabel)"]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        do {
            try process.run()
            process.waitUntilExit()
            return process.terminationStatus == 0
        } catch {
            return false
        }
    }

    private static func runShell(_ command: [String]) throws {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: command[0])
        process.arguments = Array(command.dropFirst())
        let output = Pipe()
        process.standardOutput = output
        process.standardError = output
        do {
            try process.run()
            process.waitUntilExit()
            guard process.terminationStatus == 0 else {
                let data = output.fileHandleForReading.readDataToEndOfFile()
                let text = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? "commande shell échouée"
                throw BackendError.shellCommandFailed(text.isEmpty ? command.joined(separator: " ") : text)
            }
        } catch let error as BackendError {
            throw error
        } catch {
            throw BackendError.shellCommandFailed(error.localizedDescription)
        }
    }

    private static func withBootstrapLock(_ body: () throws -> Void) throws {
        let fd = open(Constants.bootstrapLockPath, O_CREAT | O_RDWR, 0o644)
        if fd == -1 {
            try body()
            return
        }
        defer {
            flock(fd, LOCK_UN)
            close(fd)
        }
        flock(fd, LOCK_EX)
        try body()
    }

    private static func httpGet(_ url: URL, timeout: TimeInterval) -> HTTPResult? {
        let semaphore = DispatchSemaphore(value: 0)
        let box = HTTPResultBox()
        var request = URLRequest(url: url)
        request.timeoutInterval = timeout
        let task = URLSession.shared.dataTask(with: request) { data, response, _ in
            defer { semaphore.signal() }
            guard let response = response as? HTTPURLResponse, let data = data else { return }
            box.value = HTTPResult(statusCode: response.statusCode, data: data)
        }
        task.resume()
        let result = semaphore.wait(timeout: .now() + timeout + 0.8)
        if result == .timedOut {
            task.cancel()
            return nil
        }
        return box.value
    }
}

final class BootMarkView: NSView {
    private let halo = NSView()
    private let core = NSView()
    private let ring = NSView()
    private let orbit = NSView()

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        translatesAutoresizingMaskIntoConstraints = false
        wantsLayer = true
        layer?.backgroundColor = .clear

        for view in [halo, orbit, ring, core] {
            view.translatesAutoresizingMaskIntoConstraints = false
            view.wantsLayer = true
            addSubview(view)
        }

        halo.layer?.backgroundColor = NSColor(calibratedRed: 0.90, green: 0.96, blue: 1.0, alpha: 0.92).cgColor
        halo.layer?.cornerRadius = 48
        halo.layer?.shadowColor = NSColor(calibratedRed: 0.48, green: 0.76, blue: 1.0, alpha: 0.45).cgColor
        halo.layer?.shadowOpacity = 1
        halo.layer?.shadowRadius = 22

        core.layer?.backgroundColor = NSColor(calibratedRed: 1.0, green: 0.98, blue: 0.92, alpha: 1).cgColor
        core.layer?.cornerRadius = 16
        core.layer?.shadowColor = NSColor(calibratedRed: 1.0, green: 0.82, blue: 0.52, alpha: 0.5).cgColor
        core.layer?.shadowOpacity = 1
        core.layer?.shadowRadius = 14

        ring.layer?.borderWidth = 3
        ring.layer?.borderColor = NSColor(calibratedRed: 1.0, green: 0.79, blue: 0.47, alpha: 0.9).cgColor
        ring.layer?.cornerRadius = 30

        orbit.layer?.borderWidth = 1
        orbit.layer?.borderColor = NSColor(calibratedRed: 0.52, green: 0.74, blue: 1.0, alpha: 0.24).cgColor
        orbit.layer?.cornerRadius = 48

        NSLayoutConstraint.activate([
            widthAnchor.constraint(equalToConstant: 96),
            heightAnchor.constraint(equalToConstant: 96),

            halo.centerXAnchor.constraint(equalTo: centerXAnchor),
            halo.centerYAnchor.constraint(equalTo: centerYAnchor),
            halo.widthAnchor.constraint(equalToConstant: 84),
            halo.heightAnchor.constraint(equalToConstant: 84),

            orbit.centerXAnchor.constraint(equalTo: centerXAnchor),
            orbit.centerYAnchor.constraint(equalTo: centerYAnchor),
            orbit.widthAnchor.constraint(equalToConstant: 92),
            orbit.heightAnchor.constraint(equalToConstant: 92),

            ring.centerXAnchor.constraint(equalTo: centerXAnchor),
            ring.centerYAnchor.constraint(equalTo: centerYAnchor),
            ring.widthAnchor.constraint(equalToConstant: 84),
            ring.heightAnchor.constraint(equalToConstant: 34),

            core.centerXAnchor.constraint(equalTo: centerXAnchor),
            core.centerYAnchor.constraint(equalTo: centerYAnchor),
            core.widthAnchor.constraint(equalToConstant: 32),
            core.heightAnchor.constraint(equalToConstant: 32),
        ])
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }
}

@MainActor
final class BootOverlayView: NSVisualEffectView {
    let phaseLabel = NSTextField(labelWithString: "IRIS SYSTEM // CLEANROOM BIOS")
    let titleLabel = NSTextField(labelWithString: "IRIS cleanroom boot")
    let messageLabel = NSTextField(labelWithString: "Réveil du bridge local et projection de la chambre opérable.")
    let detailLabel = NSTextField(labelWithString: "Attente du cockpit...")
    let progressBar = NSProgressIndicator()
    let retryButton = NSButton(title: "Réessayer", target: nil, action: nil)
    let restartButton = NSButton(title: "Relancer backend", target: nil, action: nil)
    let logsButton = NSButton(title: "Ouvrir les logs", target: nil, action: nil)
    let shellValue = NSTextField(labelWithString: "native")
    let stackValue = NSTextField(labelWithString: "autonomy")
    let userValue = NSTextField(labelWithString: Constants.operatorName)
    let targetValue = NSTextField(labelWithString: "ready-gate")
    let consoleLabel = NSTextField(wrappingLabelWithString: "[bios] cleanroom link waiting")

    private let buttonRow = NSStackView()
    private let markView = BootMarkView()

    override init(frame frameRect: NSRect) {
        super.init(frame: frameRect)
        material = .hudWindow
        blendingMode = .withinWindow
        state = .active
        wantsLayer = true
        layer?.backgroundColor = NSColor(calibratedRed: 0.97, green: 0.98, blue: 1.0, alpha: 0.86).cgColor
        translatesAutoresizingMaskIntoConstraints = false

        let panel = NSVisualEffectView()
        panel.translatesAutoresizingMaskIntoConstraints = false
        panel.material = .sidebar
        panel.blendingMode = .withinWindow
        panel.state = .active
        panel.wantsLayer = true
        panel.layer?.cornerRadius = 28
        panel.layer?.borderWidth = 1
        panel.layer?.borderColor = NSColor(calibratedRed: 0.46, green: 0.62, blue: 0.82, alpha: 0.18).cgColor
        panel.layer?.backgroundColor = NSColor(calibratedRed: 0.99, green: 0.995, blue: 1.0, alpha: 0.92).cgColor
        panel.layer?.shadowColor = NSColor(calibratedRed: 0.42, green: 0.52, blue: 0.66, alpha: 0.22).cgColor
        panel.layer?.shadowOpacity = 1
        panel.layer?.shadowRadius = 36

        let stack = NSStackView()
        stack.translatesAutoresizingMaskIntoConstraints = false
        stack.orientation = .vertical
        stack.spacing = 14

        let topline = NSStackView()
        topline.translatesAutoresizingMaskIntoConstraints = false
        topline.orientation = .horizontal
        topline.alignment = .centerY
        topline.distribution = .fillEqually

        let operatorLabel = NSTextField(labelWithString: "OPERATOR // \(Constants.operatorName.uppercased())")

        phaseLabel.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .semibold)
        phaseLabel.textColor = NSColor(calibratedRed: 0.43, green: 0.51, blue: 0.62, alpha: 0.96)
        operatorLabel.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .semibold)
        operatorLabel.textColor = NSColor(calibratedRed: 0.43, green: 0.51, blue: 0.62, alpha: 0.96)
        operatorLabel.alignment = .right

        topline.addArrangedSubview(phaseLabel)
        topline.addArrangedSubview(operatorLabel)

        let hero = NSStackView()
        hero.translatesAutoresizingMaskIntoConstraints = false
        hero.orientation = .horizontal
        hero.spacing = 18
        hero.alignment = .centerY

        let copy = NSStackView()
        copy.translatesAutoresizingMaskIntoConstraints = false
        copy.orientation = .vertical
        copy.spacing = 8

        titleLabel.font = NSFont.systemFont(ofSize: 36, weight: .heavy)
        titleLabel.textColor = NSColor(calibratedRed: 0.09, green: 0.16, blue: 0.25, alpha: 1)

        messageLabel.font = NSFont.systemFont(ofSize: 15, weight: .semibold)
        messageLabel.textColor = NSColor(calibratedRed: 0.22, green: 0.30, blue: 0.42, alpha: 1)

        detailLabel.font = NSFont.monospacedSystemFont(ofSize: 12, weight: .medium)
        detailLabel.textColor = NSColor(calibratedRed: 0.42, green: 0.51, blue: 0.63, alpha: 1)
        detailLabel.maximumNumberOfLines = 0

        copy.addArrangedSubview(titleLabel)
        copy.addArrangedSubview(messageLabel)
        copy.addArrangedSubview(detailLabel)

        hero.addArrangedSubview(markView)
        hero.addArrangedSubview(copy)

        let infoRow = NSStackView()
        infoRow.translatesAutoresizingMaskIntoConstraints = false
        infoRow.orientation = .horizontal
        infoRow.spacing = 10
        infoRow.distribution = .fillEqually
        for chip in [
            makeInfoChip(title: "user", valueLabel: userValue),
            makeInfoChip(title: "shell", valueLabel: shellValue),
            makeInfoChip(title: "stack", valueLabel: stackValue),
            makeInfoChip(title: "phase", valueLabel: targetValue),
        ] {
            infoRow.addArrangedSubview(chip)
        }

        let consolePanel = NSVisualEffectView()
        consolePanel.translatesAutoresizingMaskIntoConstraints = false
        consolePanel.material = .underWindowBackground
        consolePanel.blendingMode = .withinWindow
        consolePanel.state = .active
        consolePanel.wantsLayer = true
        consolePanel.layer?.cornerRadius = 20
        consolePanel.layer?.borderWidth = 1
        consolePanel.layer?.borderColor = NSColor(calibratedRed: 0.50, green: 0.66, blue: 0.86, alpha: 0.12).cgColor
        consolePanel.layer?.backgroundColor = NSColor(calibratedRed: 0.97, green: 0.985, blue: 1.0, alpha: 0.84).cgColor

        consoleLabel.translatesAutoresizingMaskIntoConstraints = false
        consoleLabel.font = NSFont.monospacedSystemFont(ofSize: 12, weight: .medium)
        consoleLabel.textColor = NSColor(calibratedRed: 0.23, green: 0.32, blue: 0.43, alpha: 1)
        consoleLabel.maximumNumberOfLines = 0
        consolePanel.addSubview(consoleLabel)

        progressBar.translatesAutoresizingMaskIntoConstraints = false
        progressBar.isIndeterminate = false
        progressBar.minValue = 0
        progressBar.maxValue = 100
        progressBar.doubleValue = 12
        progressBar.controlTint = .blueControlTint

        buttonRow.orientation = .horizontal
        buttonRow.spacing = 10
        buttonRow.alignment = .leading
        buttonRow.distribution = .fillProportionally
        buttonRow.translatesAutoresizingMaskIntoConstraints = false

        for button in [retryButton, restartButton, logsButton] {
            button.bezelStyle = .rounded
            button.font = NSFont.systemFont(ofSize: 13, weight: .semibold)
            button.isHidden = true
            button.contentTintColor = NSColor(calibratedRed: 0.10, green: 0.20, blue: 0.36, alpha: 1)
        }

        buttonRow.addArrangedSubview(retryButton)
        buttonRow.addArrangedSubview(restartButton)
        buttonRow.addArrangedSubview(logsButton)

        stack.addArrangedSubview(topline)
        stack.addArrangedSubview(hero)
        stack.addArrangedSubview(infoRow)
        stack.addArrangedSubview(consolePanel)
        stack.addArrangedSubview(progressBar)
        stack.addArrangedSubview(buttonRow)

        addSubview(panel)
        panel.addSubview(stack)

        NSLayoutConstraint.activate([
            panel.centerXAnchor.constraint(equalTo: centerXAnchor),
            panel.centerYAnchor.constraint(equalTo: centerYAnchor),
            panel.widthAnchor.constraint(lessThanOrEqualToConstant: 860),
            panel.widthAnchor.constraint(greaterThanOrEqualToConstant: 560),

            stack.topAnchor.constraint(equalTo: panel.topAnchor, constant: 26),
            stack.leadingAnchor.constraint(equalTo: panel.leadingAnchor, constant: 26),
            stack.trailingAnchor.constraint(equalTo: panel.trailingAnchor, constant: -26),
            stack.bottomAnchor.constraint(equalTo: panel.bottomAnchor, constant: -26),

            consoleLabel.topAnchor.constraint(equalTo: consolePanel.topAnchor, constant: 16),
            consoleLabel.leadingAnchor.constraint(equalTo: consolePanel.leadingAnchor, constant: 16),
            consoleLabel.trailingAnchor.constraint(equalTo: consolePanel.trailingAnchor, constant: -16),
            consoleLabel.bottomAnchor.constraint(equalTo: consolePanel.bottomAnchor, constant: -16),
        ])
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    private func makeInfoChip(title: String, valueLabel: NSTextField) -> NSView {
        let panel = NSVisualEffectView()
        panel.translatesAutoresizingMaskIntoConstraints = false
        panel.material = .menu
        panel.blendingMode = .withinWindow
        panel.state = .active
        panel.wantsLayer = true
        panel.layer?.cornerRadius = 16
        panel.layer?.borderWidth = 1
        panel.layer?.borderColor = NSColor(calibratedRed: 0.48, green: 0.66, blue: 0.86, alpha: 0.12).cgColor

        let titleLabel = NSTextField(labelWithString: title.uppercased())
        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        titleLabel.font = NSFont.monospacedSystemFont(ofSize: 10, weight: .semibold)
        titleLabel.textColor = NSColor(calibratedRed: 0.48, green: 0.56, blue: 0.67, alpha: 1)

        valueLabel.translatesAutoresizingMaskIntoConstraints = false
        valueLabel.font = NSFont.systemFont(ofSize: 16, weight: .bold)
        valueLabel.textColor = NSColor(calibratedRed: 0.10, green: 0.18, blue: 0.30, alpha: 1)

        panel.addSubview(titleLabel)
        panel.addSubview(valueLabel)
        NSLayoutConstraint.activate([
            titleLabel.topAnchor.constraint(equalTo: panel.topAnchor, constant: 12),
            titleLabel.leadingAnchor.constraint(equalTo: panel.leadingAnchor, constant: 12),
            titleLabel.trailingAnchor.constraint(equalTo: panel.trailingAnchor, constant: -12),
            valueLabel.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 6),
            valueLabel.leadingAnchor.constraint(equalTo: panel.leadingAnchor, constant: 12),
            valueLabel.trailingAnchor.constraint(equalTo: panel.trailingAnchor, constant: -12),
            valueLabel.bottomAnchor.constraint(equalTo: panel.bottomAnchor, constant: -12),
        ])
        return panel
    }

    private func progressValue(for phase: String) -> Double {
        let key = phase.lowercased()
        if key.contains("recovery") { return 96 }
        if key.contains("handoff") { return 88 }
        if key.contains("ready gate") { return 62 }
        if key.contains("native shell") { return 18 }
        return 24
    }

    func showBoot(phase: String, message: String, detail: String) {
        phaseLabel.stringValue = phase.uppercased()
        titleLabel.stringValue = "IRIS cleanroom boot"
        messageLabel.stringValue = message
        detailLabel.stringValue = detail
        shellValue.stringValue = "native"
        stackValue.stringValue = "autonomy"
        userValue.stringValue = Constants.operatorName
        targetValue.stringValue = detail.components(separatedBy: " // ").first?.lowercased() ?? "handoff"
        consoleLabel.stringValue = """
        [bios] \(phase.lowercased())
        [iris] \(message)
        [mesh] \(detail)
        [user] operator \(Constants.operatorName) attached
        """
        progressBar.doubleValue = progressValue(for: phase)
        for button in [retryButton, restartButton, logsButton] {
            button.isHidden = true
        }
        isHidden = false
        alphaValue = 1
    }

    func showRecovery(message: String, detail: String) {
        phaseLabel.stringValue = "IRIS SYSTEM // RECOVERY"
        titleLabel.stringValue = "IRIS recovery panel"
        messageLabel.stringValue = message
        detailLabel.stringValue = detail
        shellValue.stringValue = "native"
        stackValue.stringValue = "recovery"
        userValue.stringValue = Constants.operatorName
        targetValue.stringValue = "manual"
        consoleLabel.stringValue = """
        [recovery] \(message)
        [detail] \(detail)
        [action] retry, restart backend or open logs
        """
        progressBar.doubleValue = 98
        for button in [retryButton, restartButton, logsButton] {
            button.isHidden = false
        }
        isHidden = false
        alphaValue = 1
    }

    func hideOverlay() {
        alphaValue = 0
        isHidden = true
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
    private var window: NSWindow!
    private var webView: WKWebView!
    private let overlay = BootOverlayView()
    private var navigationTimeout: DispatchWorkItem?
    private var currentBootToken = UUID()
    private var nativeRecorder: AVAudioRecorder?
    private var nativeRecordingURL: URL?
    private var nativeMicPendingStop = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        if activateExistingInstanceIfNeeded() {
            NSApp.terminate(nil)
            return
        }

        NSApp.setActivationPolicy(.regular)
        buildMenu()
        buildWindow()
        activateWindow()
        beginLaunch(reason: "initial")
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        activateWindow()
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    private func activateExistingInstanceIfNeeded() -> Bool {
        let currentPID = ProcessInfo.processInfo.processIdentifier
        let others = NSRunningApplication.runningApplications(withBundleIdentifier: Constants.bundleID)
            .filter { $0.processIdentifier != currentPID }
        guard let existing = others.first else { return false }
        LogSink.shared.write("app:activating-existing-instance")
        existing.activate(options: [.activateAllWindows, .activateIgnoringOtherApps])
        return true
    }

    private func buildMenu() {
        let mainMenu = NSMenu()
        let appMenuItem = NSMenuItem()
        mainMenu.addItem(appMenuItem)

        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Relancer IRIS", action: #selector(retryPressed), keyEquivalent: "r")
        let restartItem = appMenu.addItem(withTitle: "Relancer le backend", action: #selector(restartPressed), keyEquivalent: "R")
        restartItem.keyEquivalentModifierMask = [.command, .shift]
        appMenu.addItem(withTitle: "Recharger le cockpit", action: #selector(reloadCockpitPressed), keyEquivalent: "l")
        let logsItem = appMenu.addItem(withTitle: "Ouvrir les logs", action: #selector(logsPressed), keyEquivalent: "j")
        logsItem.keyEquivalentModifierMask = [.command, .shift]
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quitter IRIS", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appMenuItem.submenu = appMenu
        NSApp.mainMenu = mainMenu
    }

    private func buildWindow() {
        window = NSWindow(
            contentRect: Constants.windowSize,
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = Constants.appName
        window.isReleasedWhenClosed = false
        window.minSize = Constants.minWindowSize
        window.center()
        window.setFrameAutosaveName("IRISMainWindow")

        let rootView = NSView()
        rootView.wantsLayer = true
        rootView.layer?.backgroundColor = NSColor(calibratedRed: 0.02, green: 0.04, blue: 0.08, alpha: 1).cgColor
        rootView.translatesAutoresizingMaskIntoConstraints = false

        let configuration = WKWebViewConfiguration()
        let userContentController = WKUserContentController()
        userContentController.add(self, name: "irisNative")
        let bootstrapScript = WKUserScript(
            source: """
            window.__irisNativeBridgeAvailable = true;
            window.__irisNativeBridgeVersion = "voice-1";
            """,
            injectionTime: .atDocumentStart,
            forMainFrameOnly: false
        )
        userContentController.addUserScript(bootstrapScript)
        configuration.userContentController = userContentController
        configuration.websiteDataStore = .default()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.translatesAutoresizingMaskIntoConstraints = false
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.setValue(false, forKey: "drawsBackground")
        webView.isHidden = true

        overlay.retryButton.target = self
        overlay.retryButton.action = #selector(retryPressed)
        overlay.restartButton.target = self
        overlay.restartButton.action = #selector(restartPressed)
        overlay.logsButton.target = self
        overlay.logsButton.action = #selector(logsPressed)

        rootView.addSubview(webView)
        rootView.addSubview(overlay)
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: rootView.topAnchor),
            webView.leadingAnchor.constraint(equalTo: rootView.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: rootView.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: rootView.bottomAnchor),

            overlay.topAnchor.constraint(equalTo: rootView.topAnchor),
            overlay.leadingAnchor.constraint(equalTo: rootView.leadingAnchor),
            overlay.trailingAnchor.constraint(equalTo: rootView.trailingAnchor),
            overlay.bottomAnchor.constraint(equalTo: rootView.bottomAnchor),
        ])

        let controller = NSViewController()
        controller.view = rootView
        window.contentViewController = controller
        window.makeKeyAndOrderFront(nil)
    }

    private func activateWindow() {
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        LogSink.shared.write("window:activated")
    }

    private func beginLaunch(reason: String, forceRestart: Bool = false) {
        currentBootToken = UUID()
        let token = currentBootToken
        webView.isHidden = true
        overlay.showBoot(
            phase: "IRIS SYSTEM // NATIVE SHELL",
            message: "Réveil du bridge local et projection de la chambre IRIS.",
            detail: "initialisation // \(reason)"
        )
        activateWindow()
        LogSink.shared.write("app:begin-launch reason=\(reason) forceRestart=\(forceRestart)")

        DispatchQueue.global(qos: .userInitiated).async { [token] in
            do {
                try BackendController.startIfNeeded(forceRestart: forceRestart)
                let ready = BackendController.waitUntilReady(timeout: 14) { detail in
                    DispatchQueue.main.async {
                        guard token == self.currentBootToken else { return }
                        self.overlay.showBoot(
                            phase: "IRIS SYSTEM // READY GATE",
                            message: "La stack locale répond. J’attends la readiness du cockpit.",
                            detail: detail
                        )
                    }
                }

                DispatchQueue.main.async {
                    guard token == self.currentBootToken else { return }
                    if ready {
                        self.loadCockpit()
                    } else {
                        self.overlay.showRecovery(
                            message: "IRIS n’a pas confirmé la readiness du cockpit.",
                            detail: "Le backend répond partiellement mais /api/ready ne passe pas au vert. Tu peux réessayer, relancer le backend ou ouvrir les logs."
                        )
                        self.activateWindow()
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    guard token == self.currentBootToken else { return }
                    self.overlay.showRecovery(
                        message: "Le shell natif n’a pas pu initialiser le backend.",
                        detail: error.localizedDescription
                    )
                    self.activateWindow()
                }
            }
        }
    }

    private func loadCockpit() {
        overlay.showBoot(
            phase: "IRIS SYSTEM // HANDOFF",
            message: "Backend prêt. Chargement du cockpit principal.",
            detail: "handoff // chargement de la vue opérateur"
        )

        var components = URLComponents(url: Constants.cockpitURL, resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "shell", value: "native"),
            URLQueryItem(name: "operator", value: Constants.operatorName),
            URLQueryItem(name: "nativeApp", value: "1"),
            URLQueryItem(name: "ts", value: String(Int(Date().timeIntervalSince1970 * 1000))),
        ]

        guard let url = components?.url else {
            overlay.showRecovery(
                message: "Impossible de composer l’URL du cockpit.",
                detail: Constants.cockpitURL.absoluteString
            )
            return
        }

        navigationTimeout?.cancel()
        let timeoutWork = DispatchWorkItem { [weak self] in
            guard let self else { return }
            self.overlay.showRecovery(
                message: "Le cockpit web n’a pas confirmé son chargement.",
                detail: "La fenêtre existe mais la page n’a pas signalé de fin de navigation dans le délai prévu."
            )
            self.activateWindow()
        }
        navigationTimeout = timeoutWork
        DispatchQueue.main.asyncAfter(deadline: .now() + 9, execute: timeoutWork)

        webView.load(URLRequest(url: url))
    }

    @objc private func retryPressed() {
        beginLaunch(reason: "retry")
    }

    @objc private func restartPressed() {
        beginLaunch(reason: "forced-restart", forceRestart: true)
    }

    @objc private func reloadCockpitPressed() {
        LogSink.shared.write("webview:reload-requested")
        if webView.url != nil && !webView.isHidden {
            loadCockpit()
        } else {
            beginLaunch(reason: "reload")
        }
    }

    @objc private func logsPressed() {
        BackendController.openLogs()
        LogSink.shared.write("logs:opened")
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        navigationTimeout?.cancel()
        webView.isHidden = false
        let resetScroll = "window.scrollTo(0, 0); document.documentElement.scrollTop = 0; document.body.scrollTop = 0;"
        if let scrollView = webView.enclosingScrollView {
            scrollView.contentView.scroll(to: NSPoint.zero)
            scrollView.reflectScrolledClipView(scrollView.contentView)
        }
        webView.evaluateJavaScript(resetScroll, completionHandler: nil)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
            if let scrollView = webView.enclosingScrollView {
                scrollView.contentView.scroll(to: NSPoint.zero)
                scrollView.reflectScrolledClipView(scrollView.contentView)
            }
            webView.evaluateJavaScript(resetScroll, completionHandler: nil)
        }
        overlay.hideOverlay()
        pushNativeVoiceStatus()
        activateWindow()
        LogSink.shared.write("webview:did-finish")
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        navigationTimeout?.cancel()
        LogSink.shared.write("webview:did-fail \(error.localizedDescription)")
        overlay.showRecovery(
            message: "Le cockpit web a échoué pendant la navigation.",
            detail: error.localizedDescription
        )
        activateWindow()
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        navigationTimeout?.cancel()
        LogSink.shared.write("webview:did-fail-provisional \(error.localizedDescription)")
        overlay.showRecovery(
            message: "Le cockpit web a échoué avant chargement.",
            detail: error.localizedDescription
        )
        activateWindow()
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        navigationTimeout?.cancel()
        LogSink.shared.write("webview:content-process-terminated")
        overlay.showRecovery(
            message: "Le processus du cockpit a été interrompu.",
            detail: "La fenêtre reste ouverte. Tu peux relancer IRIS, recharger le cockpit ou ouvrir les logs."
        )
        activateWindow()
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "irisNative" else { return }
        guard let body = message.body as? [String: Any], let command = body["command"] as? String else { return }
        switch command {
        case "voiceStatus":
            pushNativeVoiceStatus()
        case "toggleMic":
            if nativeRecorder?.isRecording == true {
                stopNativeMicAndTranscribe()
            } else {
                requestNativeMicAndStart()
            }
        case "cancelMic":
            cancelNativeMic()
        default:
            break
        }
    }

    func webView(_ webView: WKWebView, decideMediaCapturePermissionsFor origin: WKSecurityOrigin, initiatedBy frame: WKFrameInfo, type: WKMediaCaptureType) async -> WKPermissionDecision {
        .grant
    }

    private func pushNativeVoiceStatus() {
        if nativeRecorder?.isRecording == true {
            sendNativeVoiceState(detail: "Micro natif ouvert", tone: "live")
            return
        }
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized:
            sendNativeVoiceState(detail: "Micro natif prêt", tone: "ok")
        case .notDetermined:
            sendNativeVoiceState(detail: "Autorise le micro pour parler à IRIS", tone: "warn")
        case .denied, .restricted:
            sendNativeVoiceState(detail: "Micro natif bloqué par macOS", tone: "bad")
        @unknown default:
            sendNativeVoiceState(detail: "Statut micro inconnu", tone: "warn")
        }
    }

    private func requestNativeMicAndStart() {
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized:
            startNativeMic()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                DispatchQueue.main.async {
                    if granted {
                        self.startNativeMic()
                    } else {
                        self.sendNativeVoiceError("Permission micro refusée")
                    }
                }
            }
        default:
            sendNativeVoiceError("Micro bloqué par macOS")
        }
    }

    private func startNativeMic() {
        guard nativeRecorder?.isRecording != true else { return }
        do {
            let dir = Constants.logDir.appendingPathComponent("voice-inputs", isDirectory: true)
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            let url = dir.appendingPathComponent("native-\(Int(Date().timeIntervalSince1970 * 1000)).wav")
            let settings: [String: Any] = [
                AVFormatIDKey: Int(kAudioFormatLinearPCM),
                AVSampleRateKey: 16_000,
                AVNumberOfChannelsKey: 1,
                AVLinearPCMBitDepthKey: 16,
                AVLinearPCMIsBigEndianKey: false,
                AVLinearPCMIsFloatKey: false,
            ]
            let recorder = try AVAudioRecorder(url: url, settings: settings)
            recorder.prepareToRecord()
            guard recorder.record() else {
                sendNativeVoiceError("Impossible d’ouvrir le micro")
                return
            }
            nativeRecordingURL = url
            nativeRecorder = recorder
            nativeMicPendingStop = false
            sendNativeVoiceState(detail: "Micro natif ouvert · parle puis reclique pour envoyer", tone: "live")
            LogSink.shared.write("voice:native-mic-started")
        } catch {
            sendNativeVoiceError("Micro natif indisponible: \(error.localizedDescription)")
        }
    }

    private func cancelNativeMic() {
        guard let recorder = nativeRecorder else { return }
        recorder.stop()
        nativeRecorder = nil
        if let url = nativeRecordingURL {
            try? FileManager.default.removeItem(at: url)
        }
        nativeRecordingURL = nil
        nativeMicPendingStop = false
        pushNativeVoiceStatus()
        LogSink.shared.write("voice:native-mic-cancelled")
    }

    private func stopNativeMicAndTranscribe() {
        guard let recorder = nativeRecorder, let url = nativeRecordingURL else {
            pushNativeVoiceStatus()
            return
        }
        guard !nativeMicPendingStop else { return }
        nativeMicPendingStop = true
        recorder.stop()
        nativeRecorder = nil
        sendNativeVoiceState(detail: "Transcription locale en cours…", tone: "live")
        LogSink.shared.write("voice:native-mic-stopped")
        DispatchQueue.global(qos: .userInitiated).async {
            defer {
                try? FileManager.default.removeItem(at: url)
            }
            guard let audioData = try? Data(contentsOf: url) else {
                DispatchQueue.main.async {
                    self.nativeRecordingURL = nil
                    self.nativeMicPendingStop = false
                    self.sendNativeVoiceError("Impossible de lire l’audio natif")
                }
                return
            }
            var request = URLRequest(url: Constants.backendBase.appendingPathComponent("api/voice/transcribe"))
            request.httpMethod = "POST"
            request.setValue("audio/wav", forHTTPHeaderField: "Content-Type")
            request.httpBody = audioData
            if var components = URLComponents(url: request.url!, resolvingAgainstBaseURL: false) {
                components.queryItems = [URLQueryItem(name: "lang", value: "fr")]
                request.url = components.url
            }
            let semaphore = DispatchSemaphore(value: 0)
            let payloadBox = JSONPayloadBox()
            let errorBox = ErrorBox()
            let task = URLSession.shared.dataTask(with: request) { data, _, error in
                defer { semaphore.signal() }
                errorBox.value = error
                guard let data, error == nil else { return }
                payloadBox.value = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            }
            task.resume()
            _ = semaphore.wait(timeout: .now() + 100)
            DispatchQueue.main.async {
                self.nativeRecordingURL = nil
                self.nativeMicPendingStop = false
                if let networkError = errorBox.value {
                    self.sendNativeVoiceError("Transcription locale impossible: \(networkError.localizedDescription)")
                    return
                }
                guard let payload = payloadBox.value else {
                    self.sendNativeVoiceError("Transcription locale vide")
                    return
                }
                let text = ((payload["text"] as? String) ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                if text.isEmpty {
                    let detail = (payload["detail"] as? String) ?? "Aucune parole détectée"
                    self.sendNativeVoiceError(detail)
                    return
                }
                self.dispatchJavaScriptCallback(name: "__irisNativeVoiceDidTranscribe", argument: text)
                self.pushNativeVoiceStatus()
            }
        }
    }

    private func sendNativeVoiceError(_ message: String) {
        dispatchJavaScriptCallback(name: "__irisNativeVoiceDidError", argument: message)
        sendNativeVoiceState(detail: message, tone: "bad")
        LogSink.shared.write("voice:error \(message)")
    }

    private func sendNativeVoiceState(detail: String, tone: String, listening: Bool? = nil) {
        let payload: [String: Any] = [
            "available": true,
            "detail": detail,
            "tone": tone,
            "listening": listening ?? (nativeRecorder?.isRecording == true),
        ]
        dispatchJavaScriptCallback(name: "__irisNativeVoiceState", argument: payload)
    }

    private func dispatchJavaScriptCallback(name: String, argument: Any) {
        guard JSONSerialization.isValidJSONObject(["value": argument]) else { return }
        guard let data = try? JSONSerialization.data(withJSONObject: ["value": argument]),
              let raw = String(data: data, encoding: .utf8),
              let range = raw.range(of: "\"value\":") else { return }
        let fragment = String(raw[range.upperBound...]).dropLast()
        let script = "window.\(name)?.(\(fragment));"
        webView.evaluateJavaScript(script, completionHandler: nil)
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
