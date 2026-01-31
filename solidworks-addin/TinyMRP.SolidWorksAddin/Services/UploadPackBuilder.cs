using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;

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
                archive.CreateEntryFromFile(flatBomPath, ZipPath("bom", name));
            }
            else
            {
                Log(log, "Flat BOM file not found; skipping.");
            }

            if (!string.IsNullOrWhiteSpace(treeBomPath) && File.Exists(treeBomPath))
            {
                string name = Path.GetFileName(treeBomPath);
                archive.CreateEntryFromFile(treeBomPath, ZipPath("bom", name));
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

                foreach (string file in Directory.GetFiles(groupDir))
                {
                    string name = Path.GetFileName(file);
                    string baseName = Path.GetFileNameWithoutExtension(name);
                    if (allowedBaseNames != null && !IsAllowedDeliverable(baseName, allowedBaseNames))
                    {
                        continue;
                    }
                    string zipPath = ZipPath("deliverables", group, name);
                    archive.CreateEntryFromFile(file, zipPath);
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
                    archive.CreateEntryFromFile(path, zipPath);
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

        private static void Log(Action<string> log, string message)
        {
            if (log != null)
            {
                log(message);
            }
        }
    }
}
