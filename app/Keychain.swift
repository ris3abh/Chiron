// Keys live only in the login Keychain (service com.chiron.app), never in settings.json.
// chiron.py reads one with `Chiron --secret get <name>`, so Python never touches the Keychain API itself.
import Foundation

enum Keychain {
    static let service = "com.chiron.app"
    static let names = ["anthropic", "openai", "jev", "custom", "google"]

    // keys/ChironKeys does the reading and writing: it stays the same across builds, so macOS asks for permission once, not after every build.
    @discardableResult static func helper(_ args: [String], input: String? = nil) -> (status: Int32, out: String)? {
        let path = URL(fileURLWithPath: CommandLine.arguments[0]).resolvingSymlinksInPath().deletingLastPathComponent().appendingPathComponent("ChironKeys")
        guard FileManager.default.isExecutableFile(atPath: path.path) else { return nil }
        let p = Process(), out = Pipe(), inp = Pipe()
        p.executableURL = path; p.arguments = args; p.standardOutput = out; p.standardInput = inp; p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { return nil }
        if let input { inp.fileHandleForWriting.write(Data(input.utf8)) }
        try? inp.fileHandleForWriting.close()
        let data = out.fileHandleForReading.readDataToEndOfFile(); p.waitUntilExit()
        return (p.terminationStatus, String(decoding: data, as: UTF8.self))
    }
    static func get(_ name: String) -> String? {
        guard names.contains(name), let r = helper(["get", name]), r.status == 0 else { return nil }
        return r.out.trimmingCharacters(in: .whitespacesAndNewlines)
    }
    @discardableResult static func set(_ name: String, _ value: String) -> Bool {
        let value = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard names.contains(name), !value.isEmpty else { return false }
        return helper(["set", name], input: value)?.status == 0
    }
    @discardableResult static func delete(_ name: String) -> Bool {
        guard names.contains(name) else { return false }
        return helper(["delete", name])?.status == 0
    }
    // Settings shows "•••• last4", never the key.
    static func has(_ name: String) -> Bool { masked(name)["saved"] as? Bool == true }
    static func masked(_ name: String) -> [String: Any] {
        guard let v = get(name), !v.isEmpty else { return ["saved": false] }
        return ["saved": true, "last4": String(v.suffix(4))]
    }

    // Older installs kept the custom server's key as apiKey in settings.json. Move it once, then drop it from the file.
    static func migrate() {
        guard let old = Prefs.d["apiKey"] as? String else { return }
        if old.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || set("custom", old) {
            Prefs.remove("apiKey")
        }
    }

    // `Chiron --secret get|set|delete <name>`: set reads the value from stdin so it never shows in `ps`.
    static func cli(_ args: [String]) -> Int32 {
        guard args.count == 2, names.contains(args[1]) else {
            FileHandle.standardError.write("usage: Chiron --secret get|set|delete <\(names.joined(separator: "|"))>\n".data(using: .utf8)!); return 2
        }
        switch args[0] {
        case "get":
            guard let v = get(args[1]) else { return 1 }
            print(v); return 0
        case "set":
            let v = String(data: FileHandle.standardInput.readDataToEndOfFile(), encoding: .utf8) ?? ""
            return set(args[1], v) ? 0 : 1
        case "delete":
            return delete(args[1]) ? 0 : 1
        default:
            return 2
        }
    }
}
