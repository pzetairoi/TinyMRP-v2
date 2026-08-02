using System;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal static class MeshExportLimit
    {
        public const int DefaultMegabytes = 50;
        private const long BytesPerMegabyte = 1024L * 1024L;

        public static int NormalizeMegabytes(int value)
        {
            return value > 0 ? value : DefaultMegabytes;
        }

        public static long ToBytes(int megabytes)
        {
            return NormalizeMegabytes(megabytes) * BytesPerMegabyte;
        }

        public static bool IsMeshFormat(string format)
        {
            string normalized = (format ?? string.Empty).Trim().TrimStart('.').ToLowerInvariant();
            return normalized == "ply" || normalized == "stl" || normalized == "3mf";
        }

        public static bool IsOversized(string format, long bytes, long limitBytes)
        {
            return IsMeshFormat(format) && limitBytes > 0 && bytes > limitBytes;
        }

        public static long EstimateBytes(string format, int triangleCount)
        {
            if (!IsMeshFormat(format) || triangleCount <= 0)
            {
                return 0;
            }

            string normalized = (format ?? string.Empty).Trim().TrimStart('.').ToLowerInvariant();
            long bytesPerTriangle = normalized == "ply" ? 49L : 50L;
            long headerBytes = normalized == "3mf" ? 1024L : 256L;
            return headerBytes + bytesPerTriangle * triangleCount;
        }

        public static string Describe(long bytes, long limitBytes)
        {
            double actualMb = bytes / (double)BytesPerMegabyte;
            double limitMb = limitBytes / (double)BytesPerMegabyte;
            return "mesh output is " + actualMb.ToString("0.0") + " MB; limit is " +
                   limitMb.ToString("0.0") + " MB";
        }
    }
}
