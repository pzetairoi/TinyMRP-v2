using System;
using System.Collections.Generic;
using System.IO;
using System.Web.Script.Serialization;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal static class AssociatedFilesStore
    {
        private const string SidecarSuffix = ".tinymrp-associated-files.json";

        private sealed class StoreData
        {
            public int Version { get; set; } = 1;
            public Dictionary<string, string> Configurations { get; set; } =
                new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        }

        public static AssociatedFilesPayload Load(string modelPath, string configurationName, string legacyJson)
        {
            StoreData data = ReadStore(modelPath);
            string key = configurationName ?? string.Empty;
            if (data != null && data.Configurations != null &&
                data.Configurations.TryGetValue(key, out string json))
            {
                return AssociatedFilesPayload.FromJson(json);
            }

            // Existing documents may still contain the old read-only property. It is never changed;
            // the next user save migrates the payload to the sidecar.
            return AssociatedFilesPayload.FromJson(legacyJson);
        }

        public static void Save(string modelPath, string configurationName, AssociatedFilesPayload payload)
        {
            if (string.IsNullOrWhiteSpace(modelPath))
            {
                throw new InvalidOperationException("Save the SolidWorks document before managing associated files.");
            }

            StoreData data = ReadStore(modelPath) ?? new StoreData();
            if (data.Configurations == null)
            {
                data.Configurations = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            }

            data.Configurations[configurationName ?? string.Empty] =
                (payload ?? new AssociatedFilesPayload()).ToJson();

            string path = GetSidecarPath(modelPath);
            TextFileHelper.WriteAllTextUtf8NoBom(path, new JavaScriptSerializer().Serialize(data));
        }

        public static void CopyForRenamedDocument(string sourceModelPath, string targetModelPath)
        {
            string source = GetSidecarPath(sourceModelPath);
            string target = GetSidecarPath(targetModelPath);
            if (string.IsNullOrWhiteSpace(source) || string.IsNullOrWhiteSpace(target) || !File.Exists(source))
            {
                return;
            }

            File.Copy(source, target, true);
        }

        public static void DeleteForDocument(string modelPath)
        {
            string path = GetSidecarPath(modelPath);
            if (!string.IsNullOrWhiteSpace(path) && File.Exists(path))
            {
                File.Delete(path);
            }
        }

        internal static string GetSidecarPath(string modelPath)
        {
            return string.IsNullOrWhiteSpace(modelPath) ? string.Empty : modelPath + SidecarSuffix;
        }

        private static StoreData ReadStore(string modelPath)
        {
            string path = GetSidecarPath(modelPath);
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                return null;
            }

            try
            {
                return new JavaScriptSerializer().Deserialize<StoreData>(File.ReadAllText(path));
            }
            catch
            {
                return null;
            }
        }
    }
}
