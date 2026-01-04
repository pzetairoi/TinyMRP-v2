using System;
using System.Collections.Generic;
using System.IO;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal sealed class TinyMrpConfig
    {
        public string BlankTemplatePath { get; set; }
        public bool RemoveModifiedNotes { get; set; }
        public string FilterAny { get; set; }
        public string BomTemplatePath { get; set; }
        public string WebLink { get; set; }
        public string BackendUrl { get; set; }
        public string AuthToken { get; set; }
        public string BomFolder { get; set; }
        public string DeliverablesFolder { get; set; }
        public string NumberingSchemeId { get; set; }
        public string NumberingContextDefaults { get; set; }
        public string AddinDirectory { get; private set; }
        public string ConfigPath { get; private set; }

        public static TinyMrpConfig Load(string addinDirectory)
        {
            var config = new TinyMrpConfig();
            config.AddinDirectory = addinDirectory;
            string addinConfigPath = Path.Combine(addinDirectory, "TinyMRP_config.txt");
            string userConfigPath = config.GetUserConfigPath();
            config.ConfigPath = File.Exists(userConfigPath) ? userConfigPath : addinConfigPath;
            config.SetDefaults();

            if (File.Exists(config.ConfigPath))
            {
                foreach (string rawLine in File.ReadAllLines(config.ConfigPath))
                {
                    string line = rawLine.Trim();
                    if (line.Length == 0 || line.StartsWith("#") || line.StartsWith(";"))
                    {
                        continue;
                    }

                    int idx = line.IndexOf('=');
                    if (idx <= 0)
                    {
                        continue;
                    }

                    string key = line.Substring(0, idx).Trim();
                    string value = line.Substring(idx + 1).Trim();
                    config.Apply(key, value);
                }
            }
            else
            {
                config.Save();
            }

            config.ResolvePaths();
            return config;
        }

        private void SetDefaults()
        {
            BlankTemplatePath = "Templates\\TinyMRP_BLANKSHEET_TEMPLATE.slddrt";
            BomTemplatePath = "Templates\\TinyMRP_BOM_TEMPLATE.sldbomtbt";
            RemoveModifiedNotes = true;
            FilterAny = "*";
            WebLink = "localhost:5000";
            BackendUrl = "http://localhost:5000";
            AuthToken = string.Empty;
            BomFolder = "Output";
            DeliverablesFolder = "Output";
            NumberingSchemeId = string.Empty;
            NumberingContextDefaults = "type=PART;family=;subfamily=;project=;site=";
        }

        private void Apply(string key, string value)
        {
            switch (key)
            {
                case "BlankTemplatePath":
                    BlankTemplatePath = value;
                    break;
                case "REMOVE_MODIFIED_NOTES":
                    RemoveModifiedNotes = ParseBool(value, RemoveModifiedNotes);
                    break;
                case "FILTER_ANY":
                    FilterAny = value;
                    break;
                case "BOMtemplate":
                    BomTemplatePath = value;
                    break;
                case "weblink":
                    WebLink = value;
                    break;
                case "BackendUrl":
                    BackendUrl = value;
                    break;
                case "AuthToken":
                    AuthToken = value;
                    break;
                case "BOM_Folder":
                    BomFolder = value;
                    break;
                case "deliverables_folder":
                    DeliverablesFolder = value;
                    break;
                case "NumberingSchemeId":
                    NumberingSchemeId = value;
                    break;
                case "NumberingContextDefaults":
                    NumberingContextDefaults = value;
                    break;
            }
        }

        public void ResolvePaths()
        {
            BlankTemplatePath = ResolvePath(BlankTemplatePath);
            BomTemplatePath = ResolvePath(BomTemplatePath);
            BomFolder = ResolvePath(BomFolder);
            DeliverablesFolder = ResolvePath(DeliverablesFolder);
        }

        private string ResolvePath(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return path;
            }

            if (Path.IsPathRooted(path))
            {
                return path;
            }

            return Path.Combine(AddinDirectory ?? string.Empty, path);
        }

        public void Save()
        {
            var lines = new List<string>
            {
                "BlankTemplatePath=" + GetPathForConfig(BlankTemplatePath),
                "REMOVE_MODIFIED_NOTES=" + (RemoveModifiedNotes ? "True" : "False"),
                "FILTER_ANY=" + (FilterAny ?? string.Empty),
                "BOMtemplate=" + GetPathForConfig(BomTemplatePath),
                "weblink=" + (WebLink ?? string.Empty),
                "BackendUrl=" + (BackendUrl ?? string.Empty),
                "AuthToken=" + (AuthToken ?? string.Empty),
                "BOM_Folder=" + GetPathForConfig(BomFolder),
                "deliverables_folder=" + GetPathForConfig(DeliverablesFolder),
                "NumberingSchemeId=" + (NumberingSchemeId ?? string.Empty),
                "NumberingContextDefaults=" + (NumberingContextDefaults ?? string.Empty),
            };

            try
            {
                WriteConfig(ConfigPath, lines);
            }
            catch (Exception ex) when (ex is UnauthorizedAccessException || ex is IOException)
            {
                ConfigPath = GetUserConfigPath();
                WriteConfig(ConfigPath, lines);
            }
        }

        private void WriteConfig(string path, List<string> lines)
        {
            string dir = Path.GetDirectoryName(path);
            if (!string.IsNullOrWhiteSpace(dir))
            {
                Directory.CreateDirectory(dir);
            }

            File.WriteAllLines(path, lines.ToArray());
        }

        private string GetUserConfigPath()
        {
            string baseDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "TinyMRP");
            return Path.Combine(baseDir, "TinyMRP_config.txt");
        }

        private string GetPathForConfig(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return string.Empty;
            }

            if (!string.IsNullOrEmpty(AddinDirectory) &&
                path.StartsWith(AddinDirectory, StringComparison.OrdinalIgnoreCase))
            {
                string relative = path.Substring(AddinDirectory.Length)
                    .TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                return relative.Length == 0 ? "." : relative;
            }

            return path;
        }

        private static bool ParseBool(string value, bool fallback)
        {
            bool result;
            return bool.TryParse(value, out result) ? result : fallback;
        }
    }
}
