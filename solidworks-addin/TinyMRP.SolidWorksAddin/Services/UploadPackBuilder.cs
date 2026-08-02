using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Web.Script.Serialization;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal static class UploadPackBuilder
    {
        internal sealed class AssociatedFilesBundle
        {
            public string PartNumber { get; set; }
            public string Revision { get; set; }
            public List<AssociatedFileEntry> Files { get; set; } = new List<AssociatedFileEntry>();
        }

        private static readonly string[] DeliverableGroups = new[]
        {
            "png",
            "pdf",
            "dxf",
            "step",
            "edr",
            "3mf",
            "ply",
            "stl",
            "datasheet"
        };

        public static string RevToken(string rev)
        {
            return string.IsNullOrWhiteSpace(rev) ? "__no_rev__" : rev;
        }

        public static void Build(
            string zipPath,
            string deliverablesRoot,
            string flatBomPath,
            string treeBomPath,
            IEnumerable<AssociatedFilesBundle> extraBundles,
            Action<string> log,
            ICollection<string> allowedBaseNames = null,
            ICollection<string> allowedGroups = null)
        {
            if (string.IsNullOrWhiteSpace(zipPath))
            {
                throw new ArgumentException("zipPath required");
            }

            if (File.Exists(zipPath))
            {
                File.Delete(zipPath);
            }

            using (var archive = ZipFile.Open(zipPath, ZipArchiveMode.Create))
            {
                AddBom(archive, flatBomPath, treeBomPath, log);
                AddDeliverables(archive, deliverablesRoot, log, allowedBaseNames, allowedGroups);
                AddExtras(archive, extraBundles, log);
            }
        }

        private static void AddBom(ZipArchive archive, string flatBomPath, string treeBomPath, Action<string> log)
        {
            if (!string.IsNullOrWhiteSpace(flatBomPath) && File.Exists(flatBomPath))
            {
                string name = Path.GetFileName(flatBomPath);
                archive.CreateEntryFromFile(flatBomPath, ZipPath("bom", name), CompressionLevel.Fastest);
            }
            else
            {
                Log(log, "Flat BOM file not found; skipping.");
            }

            if (!string.IsNullOrWhiteSpace(treeBomPath) && File.Exists(treeBomPath))
            {
                string name = Path.GetFileName(treeBomPath);
                archive.CreateEntryFromFile(treeBomPath, ZipPath("bom", name), CompressionLevel.Fastest);
            }
            else
            {
                Log(log, "Tree BOM file not found; skipping.");
            }
        }

        private static void AddDeliverables(
            ZipArchive archive,
            string deliverablesRoot,
            Action<string> log,
            ICollection<string> allowedBaseNames,
            ICollection<string> allowedGroups)
        {
            if (string.IsNullOrWhiteSpace(deliverablesRoot) || !Directory.Exists(deliverablesRoot))
            {
                Log(log, "Deliverables folder not found; skipping.");
                return;
            }

            if (allowedGroups != null && allowedGroups.Count == 0)
            {
                Log(log, "Upload pack: no deliverable groups selected; skipping deliverables.");
                return;
            }

            if (allowedBaseNames != null && allowedBaseNames.Count == 0)
            {
                Log(log, "Upload pack: no deliverable keys found; skipping deliverables.");
                return;
            }

            foreach (string group in DeliverableGroups)
            {
                if (allowedGroups != null && !allowedGroups.Contains(group))
                {
                    continue;
                }
                string groupDir = Path.Combine(deliverablesRoot, group);
                if (!Directory.Exists(groupDir))
                {
                    continue;
                }

                foreach (string file in Directory.EnumerateFiles(groupDir))
                {
                    string name = Path.GetFileName(file);
                    if (IsTransientOrFailedArtifact(name))
                    {
                        Log(log, "Upload pack skipped transient or failed export artifact: " + file);
                        continue;
                    }

                    string baseName = Path.GetFileNameWithoutExtension(name);
                    if (allowedBaseNames != null && !IsAllowedDeliverable(baseName, allowedBaseNames))
                    {
                        continue;
                    }
                    string zipPath = ZipPath("deliverables", group, name);
                    archive.CreateEntryFromFile(file, zipPath, CompressionLevel.Fastest);
                }
            }
        }

        private static void AddExtras(
            ZipArchive archive,
            IEnumerable<AssociatedFilesBundle> extraBundles,
            Action<string> log)
        {
            if (extraBundles == null)
            {
                return;
            }

            var manifest = new List<Dictionary<string, object>>();
            foreach (AssociatedFilesBundle bundle in extraBundles)
            {
                if (bundle == null)
                {
                    continue;
                }

                if (string.IsNullOrWhiteSpace(bundle.PartNumber))
                {
                    Log(log, "Associated files missing part number; skipping extras.");
                    continue;
                }

                if (bundle.Files == null || bundle.Files.Count == 0)
                {
                    continue;
                }

                string revToken = RevToken(bundle.Revision);
                foreach (AssociatedFileEntry entry in bundle.Files)
                {
                    if (entry == null || string.IsNullOrWhiteSpace(entry.Path))
                    {
                        continue;
                    }

                    string path = entry.Path;
                    if (!File.Exists(path))
                    {
                        Log(log, "Missing associated file: " + path);
                        continue;
                    }

                    string name = Path.GetFileName(path);
                    string zipPath = ZipPath("extra", bundle.PartNumber, revToken, name);
                    archive.CreateEntryFromFile(path, zipPath, CompressionLevel.Fastest);

                    string label = entry.Label ?? string.Empty;
                    string ext = entry.Extension ?? string.Empty;
                    if (string.IsNullOrWhiteSpace(ext))
                    {
                        ext = Path.GetExtension(name) ?? string.Empty;
                    }
                    ext = ext.TrimStart('.').ToLowerInvariant();
                    manifest.Add(new Dictionary<string, object>
                    {
                        ["pn"] = bundle.PartNumber ?? string.Empty,
                        ["rev"] = bundle.Revision ?? string.Empty,
                        ["name"] = name ?? string.Empty,
                        ["label"] = label,
                        ["ext"] = ext
                    });
                }
            }

            if (manifest.Count > 0)
            {
                try
                {
                    var serializer = new JavaScriptSerializer();
                    var payload = new Dictionary<string, object>
                    {
                        ["version"] = 1,
                        ["files"] = manifest
                    };
                    string json = serializer.Serialize(payload);
                    var entry = archive.CreateEntry(ZipPath("extra", "_manifest.json"));
                    using (var stream = entry.Open())
                    {
                        byte[] bytes = new UTF8Encoding(false).GetBytes(json ?? string.Empty);
                        stream.Write(bytes, 0, bytes.Length);
                    }
                }
                catch (Exception ex)
                {
                    Log(log, "Failed to write extra manifest: " + ex.Message);
                }
            }
        }

        private static string ZipPath(params string[] parts)
        {
            return string.Join("/", parts).Replace("\\", "/");
        }

        private static bool IsAllowedDeliverable(string baseName, ICollection<string> allowedBaseNames)
        {
            if (string.IsNullOrWhiteSpace(baseName) || allowedBaseNames == null)
            {
                return false;
            }

            foreach (string allowed in allowedBaseNames)
            {
                if (string.IsNullOrWhiteSpace(allowed))
                {
                    continue;
                }
                if (baseName.StartsWith(allowed, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            return false;
        }

        internal static bool IsTransientOrFailedArtifact(string path)
        {
            string name = Path.GetFileName(path ?? string.Empty);
            if (string.IsNullOrWhiteSpace(name))
            {
                return false;
            }

            return name.StartsWith("~$", StringComparison.OrdinalIgnoreCase) ||
                   name.EndsWith(".tmp", StringComparison.OrdinalIgnoreCase) ||
                   name.IndexOf(".tmp.", StringComparison.OrdinalIgnoreCase) >= 0 ||
                   name.EndsWith(".bad", StringComparison.OrdinalIgnoreCase) ||
                   name.IndexOf(".bad.", StringComparison.OrdinalIgnoreCase) >= 0 ||
                   name.EndsWith(".replacebak", StringComparison.OrdinalIgnoreCase) ||
                   name.IndexOf(".replacebak.", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private static void Log(Action<string> log, string message)
        {
            if (log != null)
            {
                log(message);
            }
        }
    }
}
