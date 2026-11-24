import Foundation
import CoreGraphics
import ImageIO
import Vision

// Decode the downloaded image and inspect its first and last content without opening an app.
func verifyImage(path: String, marker: String, ending: String) throws -> [String: Any] {
    let started = DispatchTime.now().uptimeNanoseconds
    let data = try Data(contentsOf: URL(fileURLWithPath: path))
    guard data.starts(with: [137, 80, 78, 71, 13, 10, 26, 10]),
          let source = CGImageSourceCreateWithData(data as CFData, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, [kCGImageSourceShouldCacheImmediately: true] as CFDictionary),
          image.width > 0, image.height > 0, image.width <= 20000, image.height <= 100000,
          image.width * image.height <= 120000000 else {
        throw NSError(domain: "EmailImageVerification", code: 1)
    }
    let cropHeight = min(image.height, 1600)
    let regions: [(String, CGRect)] = [
        ("top", CGRect(x: 0, y: 0, width: image.width, height: cropHeight)),
        ("bottom", CGRect(x: 0, y: image.height - cropHeight, width: image.width, height: cropHeight))
    ]
    var lines = [[String: Any]]()
    func recognize(_ crop: CGImage, region: String, level: VNRequestTextRecognitionLevel = .accurate) throws {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = level
        request.usesLanguageCorrection = false
        request.recognitionLanguages = ["en-US"]
        request.minimumTextHeight = 0.003
        try VNImageRequestHandler(cgImage: crop).perform([request])
        for result in request.results ?? [] {
            if let candidate = result.topCandidates(1).first {
                lines.append(["region": region, "text": candidate.string, "confidence": candidate.confidence])
            }
        }
    }
    for (name, rect) in regions {
        if let crop = image.cropping(to: rect) { try recognize(crop, region: name) }
    }
    // Padding keeps a flush top-edge marker away from Vision's image-boundary detection.
    let stripWidth = min(image.width, 960)
    if let strip = image.cropping(to: CGRect(x: (image.width - stripWidth) / 2, y: 0,
                                           width: stripWidth, height: min(image.height, 80))) {
        let scale = 2, padding = 32
        let width = (strip.width + padding * 2) * scale
        let height = (strip.height + padding * 2) * scale
        if let context = CGContext(data: nil, width: width, height: height, bitsPerComponent: 8,
                                   bytesPerRow: width * 4, space: CGColorSpaceCreateDeviceRGB(),
                                   bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) {
            context.setFillColor(CGColor(gray: 1, alpha: 1))
            context.fill(CGRect(x: 0, y: 0, width: width, height: height))
            context.interpolationQuality = .high
            context.draw(strip, in: CGRect(x: padding * scale, y: padding * scale,
                                          width: strip.width * scale, height: strip.height * scale))
            if let padded = context.makeImage() { try recognize(padded, region: "padded-top-marker", level: .fast) }
        }
    }
    func normalized(_ text: String) -> String {
        text.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ").uppercased()
    }
    let text = normalized(lines.compactMap { $0["text"] as? String }.joined(separator: " "))
    let markerFound = text.contains(normalized(marker))
    let endingFound = text.contains(normalized(ending))
    let elapsed = Double(DispatchTime.now().uptimeNanoseconds - started) / 1_000_000
    return ["ok": markerFound && endingFound, "decodedPNG": true, "width": image.width,
            "height": image.height, "markerFound": markerFound, "endingFound": endingFound,
            "marker": marker, "ending": ending, "elapsedMs": elapsed,
            "inspectedAt": ISO8601DateFormatter().string(from: Date()), "textLines": lines]
}

guard CommandLine.arguments.count == 3 || CommandLine.arguments.count == 4 else {
    fputs("Usage: verify-email-image IMAGE_PATH MARKER [ENDING]\n", stderr)
    exit(2)
}
do {
    let result = try verifyImage(path: CommandLine.arguments[1], marker: CommandLine.arguments[2],
                                 ending: CommandLine.arguments.count == 4 ? CommandLine.arguments[3] : "Update Email Preference")
    let output = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
    FileHandle.standardOutput.write(output)
    FileHandle.standardOutput.write(Data([10]))
    exit(result["ok"] as? Bool == true ? 0 : 1)
} catch {
    let output: [String: Any] = ["ok": false, "decodedPNG": false, "error": "IMAGE_DECODE_OR_OCR_FAILED"]
    if let data = try? JSONSerialization.data(withJSONObject: output, options: [.sortedKeys]) {
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data([10]))
    }
    exit(2)
}
