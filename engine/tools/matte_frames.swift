// matte_frames.swift: person mattes for a folder of frames, with the Mac's own Vision segmentation (free, local).
// Usage: swift matte_frames.swift <frames_dir> <out_dir> [accurate|balanced|fast]
// Writes <out_dir>/<same name>.png: a grayscale mask (white = person) at the frame's size.
import Foundation
import Vision
import CoreImage
import ImageIO
import UniformTypeIdentifiers

let args = CommandLine.arguments
guard args.count >= 3 else { print("usage: matte_frames.swift <frames_dir> <out_dir> [accurate|balanced|fast]"); exit(1) }
let inDir = URL(fileURLWithPath: args[1]), outDir = URL(fileURLWithPath: args[2])
let level: VNGeneratePersonSegmentationRequest.QualityLevel =
  args.count > 3 ? (args[3] == "fast" ? .fast : args[3] == "balanced" ? .balanced : .accurate) : .accurate
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
let files = try FileManager.default.contentsOfDirectory(at: inDir, includingPropertiesForKeys: nil)
  .filter { ["png", "jpg", "jpeg"].contains($0.pathExtension.lowercased()) }
  .sorted { $0.lastPathComponent < $1.lastPathComponent }
let ctx = CIContext()
let req = VNGeneratePersonSegmentationRequest()
req.qualityLevel = level
req.outputPixelFormat = kCVPixelFormatType_OneComponent8
var done = 0
for f in files {
  guard let img = CIImage(contentsOf: f) else { continue }
  let h = VNImageRequestHandler(ciImage: img, options: [:])
  try h.perform([req])
  guard let buf = req.results?.first?.pixelBuffer else { continue }
  var m = CIImage(cvPixelBuffer: buf)
  m = m.transformed(by: CGAffineTransform(scaleX: img.extent.width / m.extent.width, y: img.extent.height / m.extent.height))
  let out = outDir.appendingPathComponent(f.deletingPathExtension().lastPathComponent + ".png")
  guard let cg = ctx.createCGImage(m, from: img.extent, format: .L8, colorSpace: CGColorSpaceCreateDeviceGray()) else { continue }
  let dest = CGImageDestinationCreateWithURL(out as CFURL, UTType.png.identifier as CFString, 1, nil)!
  CGImageDestinationAddImage(dest, cg, nil); CGImageDestinationFinalize(dest)
  done += 1
}
print("matted \(done)/\(files.count) frames -> \(outDir.path)")
