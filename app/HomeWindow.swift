// The one page (ui/home.html) in two windows: Home, and the same page opened at #settings in a smaller Settings window.
// The Dock icon shows only while one of them is open, so Chiron stays a menu bar app the rest of the time.
import Cocoa
import WebKit

final class HomeWindows: NSObject, NSWindowDelegate {
    var home: NSWindow?, settings: NSWindow?
    var homeWeb: WKWebView?, settingsWeb: WKWebView?
    let bridge = HomeBridge()
    var timer: Timer?

    var webs: [WKWebView] { [homeWeb, settingsWeb].compactMap { $0 } }
    var visible: Bool { [home, settings].contains { $0?.isVisible == true } }

    func openHome() { show(settingsView: false) }
    func openSettings() { show(settingsView: true) }

    private func show(settingsView: Bool) {
        if let w = settingsView ? settings : home {
            NSApp.setActivationPolicy(.regular); NSApp.activate(ignoringOtherApps: true); w.makeKeyAndOrderFront(nil); return
        }
        let size = settingsView ? NSSize(width: 560, height: 680) : NSSize(width: 880, height: 720)
        let w = NSWindow(contentRect: NSRect(origin: .zero, size: size), styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                         backing: .buffered, defer: false)
        w.title = settingsView ? L("menu.settings").replacingOccurrences(of: "…", with: "") : "Chiron"   // still read by VoiceOver and the Window menu
        w.titlebarAppearsTransparent = true; w.titleVisibility = .hidden; w.isMovableByWindowBackground = true
        w.minSize = settingsView ? NSSize(width: 420, height: 480) : NSSize(width: 640, height: 560)
        w.isReleasedWhenClosed = false; w.delegate = self
        w.setFrameAutosaveName(settingsView ? "ChironSettings" : "ChironHome")   // remembers where the user left it
        if !w.setFrameUsingName(w.frameAutosaveName) { w.center() }
        applySharing(w)
        // The page is glass over the desktop: a vibrancy view behind a web view that draws no background of its own.
        let glass = NSVisualEffectView(frame: w.contentRect(forFrameRect: w.frame))
        glass.material = .underWindowBackground; glass.blendingMode = .behindWindow; glass.state = .active   // stays glassy when not frontmost
        let cfg = WKWebViewConfiguration()
        cfg.userContentController.add(bridge, name: "home")
        // .native tells the page it sits on real vibrancy (transparent body) under a transparent title bar (keep clear of the traffic lights).
        cfg.userContentController.addUserScript(WKUserScript(source: "document.documentElement.classList.add('native')", injectionTime: .atDocumentStart, forMainFrameOnly: true))
        let web = WKWebView(frame: glass.bounds, configuration: cfg)
        web.autoresizingMask = [.width, .height]
        web.setValue(false, forKey: "drawsBackground")
        web.underPageBackgroundColor = .clear
        bridge.attach(web)
        HomeWindows.load(web, settingsView: settingsView)
        glass.addSubview(web); w.contentView = glass
        if settingsView { settings = w; settingsWeb = web } else { home = w; homeWeb = web }
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true); w.makeKeyAndOrderFront(nil)
        startTimer()
    }

    // A file URL with read access to ui/, so strings/*.json and fonts/*.woff2 load as relative files.
    // The page's own CSP keeps it off the network.
    static func load(_ web: WKWebView, settingsView: Bool) {
        let ui = URL(fileURLWithPath: dir + "/ui", isDirectory: true)
        var page = URLComponents(url: ui.appendingPathComponent("home.html"), resolvingAgainstBaseURL: false)!
        if settingsView { page.fragment = "settings" }
        web.loadFileURL(page.url ?? ui.appendingPathComponent("home.html"), allowingReadAccessTo: ui)
    }

    // Fresh state every 5 s while a window shows it, and right after every ask (App calls refresh()).
    func startTimer() {
        guard timer == nil else { return }
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            guard let self, self.visible else { return }
            self.refresh()
        }
    }
    func refresh() {
        guard !webs.isEmpty else { return }
        bridge.homeState { [weak self] state in self?.push("state", state) }
    }
    func push(_ event: String, _ data: Any) { webs.forEach { callJS($0, "bridge.push", [event, data]) } }

    func windowWillClose(_ n: Notification) {
        guard let w = n.object as? NSWindow else { return }
        let web = w === home ? homeWeb : settingsWeb
        web?.configuration.userContentController.removeScriptMessageHandler(forName: "home")
        bridge.detach(web)
        if w === home { home = nil; homeWeb = nil } else { settings = nil; settingsWeb = nil }
        if home == nil && settings == nil {
            timer?.invalidate(); timer = nil
            NSApp.setActivationPolicy(.accessory)   // back to a menu bar app: no Dock icon
        }
    }
}
