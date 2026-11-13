import AVFoundation
import ImageIO
import UniformTypeIdentifiers

// usage: mov2gif <in.mov> <out.gif> <width> <fps> [x y w h]  (x y w h を付けると、その範囲を切り抜いてから縮小する。記事用、M22)
let a = CommandLine.arguments
let asset = AVURLAsset(url: URL(fileURLWithPath: a[1]))
let width = CGFloat(Double(a[3])!)
let fps = Double(a[4])!
let dur = CMTimeGetSeconds(asset.duration)
let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true
gen.requestedTimeToleranceBefore = .zero
gen.requestedTimeToleranceAfter = .zero
let n = Int(dur * fps)
let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: a[2]) as CFURL, UTType.gif.identifier as CFString, n, nil)!
CGImageDestinationSetProperties(dest, [kCGImagePropertyGIFDictionary: [kCGImagePropertyGIFLoopCount: 0]] as CFDictionary)
let frameProps = [kCGImagePropertyGIFDictionary: [kCGImagePropertyGIFDelayTime: 1.0 / fps]] as CFDictionary
for i in 0..<n {
    let t = CMTime(seconds: Double(i) / fps, preferredTimescale: 600)
    guard let full = try? gen.copyCGImage(at: t, actualTime: nil) else { continue }
    let img = a.count > 8 ? full.cropping(to: CGRect(x: Double(a[5])!, y: Double(a[6])!, width: Double(a[7])!, height: Double(a[8])!))! : full
    let h = CGFloat(img.height) * width / CGFloat(img.width)
    let ctx = CGContext(data: nil, width: Int(width), height: Int(h), bitsPerComponent: 8, bytesPerRow: 0,
                        space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    ctx.interpolationQuality = .high
    ctx.draw(img, in: CGRect(x: 0, y: 0, width: width, height: h))
    CGImageDestinationAddImage(dest, ctx.makeImage()!, frameProps)
}
print(CGImageDestinationFinalize(dest) ? "ok frames=\(n)" : "failed")
