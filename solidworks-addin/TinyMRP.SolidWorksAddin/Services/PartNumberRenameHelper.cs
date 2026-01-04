using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal enum RenameMode
    {
        Safe,
        RenameIfNotReferenced
    }

    internal sealed class RenameDecision
    {
        public bool Allowed { get; }
        public string Reason { get; }

        public RenameDecision(bool allowed, string reason)
        {
            Allowed = allowed;
            Reason = reason ?? string.Empty;
        }
    }

    internal static class PartNumberRenameHelper
    {
        public static string BuildBaseName(string partNumber, string revision, bool appendRevision)
        {
            string baseName = SanitizeFileName(partNumber ?? string.Empty);
            if (appendRevision && !string.IsNullOrWhiteSpace(revision))
            {
                string rev = SanitizeFileName(revision);
                if (!string.IsNullOrWhiteSpace(rev))
                {
                    baseName = baseName + "-" + rev;
                }
            }
            return baseName.Trim();
        }

        public static string SanitizeFileName(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                return string.Empty;
            }

            var invalid = new HashSet<char>(Path.GetInvalidFileNameChars());
            var cleaned = value.Trim().Select(ch =>
            {
                if (invalid.Contains(ch) || char.IsControl(ch))
                {
                    return '_';
                }
                return ch;
            }).ToArray();

            string output = new string(cleaned).Trim();
            while (output.Contains("__"))
            {
                output = output.Replace("__", "_");
            }
            return output.Trim('_', ' ');
        }

        public static string EnsureUniquePath(string directory, string baseName, string extension, Func<string, bool> exists)
        {
            if (exists == null)
            {
                exists = File.Exists;
            }

            if (string.IsNullOrWhiteSpace(directory))
            {
                directory = Directory.GetCurrentDirectory();
            }

            string safeBase = string.IsNullOrWhiteSpace(baseName) ? "Part" : baseName;
            string ext = extension ?? string.Empty;
            if (ext.Length > 0 && !ext.StartsWith(".", StringComparison.Ordinal))
            {
                ext = "." + ext;
            }

            string candidate = Path.Combine(directory, safeBase + ext);
            if (!exists(candidate))
            {
                return candidate;
            }

            for (int i = 1; i < 1000; i++)
            {
                string withSuffix = Path.Combine(directory, safeBase + "_" + i + ext);
                if (!exists(withSuffix))
                {
                    return withSuffix;
                }
            }

            return Path.Combine(directory, safeBase + "_" + DateTime.Now.ToString("yyyyMMddHHmmss") + ext);
        }

        public static bool TryBuildTargetPath(
            string currentPath,
            string partNumber,
            string revision,
            bool appendRevision,
            Func<string, bool> exists,
            out string targetPath,
            out string message)
        {
            targetPath = string.Empty;
            message = string.Empty;

            if (string.IsNullOrWhiteSpace(currentPath))
            {
                message = "File must be saved before it can be renamed.";
                return false;
            }

            string directory = Path.GetDirectoryName(currentPath);
            string extension = Path.GetExtension(currentPath);
            string baseName = BuildBaseName(partNumber, revision, appendRevision);
            if (string.IsNullOrWhiteSpace(baseName))
            {
                message = "Part number is required to rename.";
                return false;
            }

            targetPath = EnsureUniquePath(directory, baseName, extension, exists);
            return true;
        }

        public static RenameDecision EvaluateRenameDecision(string currentPath, bool isReferenced, RenameMode mode)
        {
            if (string.IsNullOrWhiteSpace(currentPath))
            {
                return new RenameDecision(false, "File must be saved before it can be renamed.");
            }

            if (mode == RenameMode.RenameIfNotReferenced && isReferenced)
            {
                return new RenameDecision(false, "File is referenced. Rename aborted.");
            }

            return new RenameDecision(true, string.Empty);
        }
    }
}
