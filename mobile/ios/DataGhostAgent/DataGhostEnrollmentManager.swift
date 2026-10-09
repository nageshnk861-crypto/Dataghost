import Foundation
import UIKit

public struct QrEnrollmentPayload: Codable {
    public let version: String
    public let server_url: String
    public let token: String
    public let code: String
    public let platform: String
    public let expires_at: String
}

public struct EnrollmentRegisterRequest: Codable {
    public let token: String
    public let enrollment_code: String
    public let device_name: String
    public let platform: String
    public let os_name: String
    public let os_version: String
    public let architecture: String
    public let hostname: String
    public let ip_address: String
    public let agent_version: String
}

public struct EnrollmentRegisterResponse: Codable {
    public let device_id: String
    public let device_name: String
    public let platform: String
    public let status: String
    public let auth_token: String?
    public let heartbeat_interval_seconds: Int
    public let server_time: String
    public let message: String
}

public class DataGhostEnrollmentManager {
    public static let shared = DataGhostEnrollmentManager()
    private init() {}

    public func parseQrCode(jsonString: String) -> QrEnrollmentPayload? {
        guard let data = jsonString.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(QrEnrollmentPayload.self, from: data)
    }

    public func registerDevice(serverUrl: String, token: String, code: String, completion: @escaping (Result<EnrollmentRegisterResponse, Error>) -> Void) {
        guard let endpoint = URL(string: "\(serverUrl.trimmingCharacters(in: CharacterSet(charactersIn: "/")))/api/devices/enrollment/register") else {
            completion(.failure(NSError(domain: "DataGhost", code: 400, userInfo: [NSLocalizedDescriptionKey: "Invalid Server URL"])))
            return
        }

        let deviceName = UIDevice.current.name
        let osVersion = "iOS \(UIDevice.current.systemVersion)"
        
        let reqPayload = EnrollmentRegisterRequest(
            token: token,
            enrollment_code: code,
            device_name: deviceName.isEmpty ? "iPhone Endpoint" : deviceName,
            platform: "iOS",
            os_name: "iOS",
            os_version: osVersion,
            architecture: "arm64",
            hostname: UIDevice.current.name,
            ip_address: "192.168.1.101",
            agent_version: "1.0.0"
        )

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")

        do {
            request.httpBody = try JSONEncoder().encode(reqPayload)
        } catch {
            completion(.failure(error))
            return
        }

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }
            guard let data = data, let httpResp = response as? HTTPURLResponse, (200...299).contains(httpResp.statusCode) else {
                completion(.failure(NSError(domain: "DataGhost", code: 500, userInfo: [NSLocalizedDescriptionKey: "Enrollment failed"])))
                return
            }

            do {
                let resp = try JSONDecoder().decode(EnrollmentRegisterResponse.self, from: data)
                UserDefaults.standard.set(resp.device_id, forKey: "dg_device_id")
                UserDefaults.standard.set(resp.auth_token, forKey: "dg_auth_token")
                UserDefaults.standard.set(serverUrl, forKey: "dg_server_url")
                completion(.success(resp))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }
}
