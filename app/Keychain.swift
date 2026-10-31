// Keys live only in the login Keychain (service com.chiron.app), never in settings.json.
// chiron.py reads one with `Chiron --secret get <name>`, so Python never touches the Keychain API itself.
import Foundation
import Security

enum Keychain {
    static let service = "com.chiron.app"
    static let names = ["anthropic", "openai", "jev", "custom", "google"]

    static func query(_ name: String) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: name]
    }
    static func get(_ name: String) -> String? {
        guard names.contains(name) else { return nil }
        var q = query(name); q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: CFTypeRef?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let data = out as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
    @discardableResult static func set(_ name: String, _ value: String) -> Bool {
        let value = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard names.contains(name), !value.isEmpty, let data = value.data(using: .utf8) else { return false }
        let found = SecItemUpdate(query(name) as CFDictionary, [kSecValueData as String: data] as CFDictionary)
        if found == errSecSuccess { return true }
        guard found == errSecItemNotFound else { return false }
        var q = query(name); q[kSecValueData as String] = data
        q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly   // never synced to iCloud or restored to another Mac
        q[kSecAttrLabel as String] = "Chiron: \(name)"
        return SecItemAdd(q as CFDictionary, nil) == errSecSuccess
    }
    @discardableResult static func delete(_ name: String) -> Bool {
        guard names.contains(name) else { return false }
        let s = SecItemDelete(query(name) as CFDictionary)
        return s == errSecSuccess || s == errSecItemNotFound
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
