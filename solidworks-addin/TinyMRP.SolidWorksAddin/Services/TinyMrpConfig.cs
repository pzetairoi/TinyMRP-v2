using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

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
        public string DxfSheetNames { get; set; }
        public string NumberingSchemeId { get; set; }
        public string NumberingContextDefaults { get; set; }
        public string PartNumberProperty { get; set; }
        public string RevisionProperty { get; set; }
        public string DisplayCodeProperty { get; set; }
        public string NumberingApplyMode { get; set; }
        public bool AutoAssignGenericNames { get; set; }
        public bool AutoAssignAnyNames { get; set; }
        public string AddinDirectory { get; private set; }
        public string ConfigPath { get; private set; }

        public static TinyMrpConfig Load(string addinDirectory)
        {
            var config = new TinyMrpConfig();
            config.AddinDirectory = addinDirectory;
            string addinConfigPath = Path.Combine(addinDirectory, "TinyMRP_config.txt");
            string machineConfigPath = config.GetMachineConfigPath();
            string userConfigPath = config.GetUserConfigPath();
            config.ConfigPath = SelectConfigPath(machineConfigPath, addinConfigPath, userConfigPath);
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
            DxfSheetNames = "flatpattern;flat_pattern;dxf;dxf sheet;DXF Sheet";
            NumberingSchemeId = string.Empty;
            NumberingContextDefaults = "type=PART;family=;subfamily=;project=;site=";
            PartNumberProperty = "PartNumber";
            RevisionProperty = "Revision";
            DisplayCodeProperty = "DisplayCode";
            NumberingApplyMode = "active_config";
            AutoAssignGenericNames = true;
            AutoAssignAnyNames = false;
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
                    AuthToken = UnprotectToken(value);
                    break;
                case "BOM_Folder":
                    BomFolder = value;
                    break;
                case "deliverables_folder":
                    DeliverablesFolder = value;
                    break;
                case "DxfSheetNames":
                    DxfSheetNames = value;
                    break;
                case "NumberingSchemeId":
                    NumberingSchemeId = value;
                    break;
                case "NumberingContextDefaults":
                    NumberingContextDefaults = value;
                    break;
                case "PartNumberProperty":
                    PartNumberProperty = value;
                    break;
                case "RevisionProperty":
                    RevisionProperty = value;
                    break;
                case "DisplayCodeProperty":
                    DisplayCodeProperty = value;
                    break;
                case "NumberingApplyMode":
                    NumberingApplyMode = value;
                    break;
                case "AutoAssignGenericNames":
                    AutoAssignGenericNames = ParseBool(value, AutoAssignGenericNames);
                    break;
                case "AutoAssignAnyNames":
                    AutoAssignAnyNames = ParseBool(value, AutoAssignAnyNames);
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
            string protectedToken = ProtectToken(AuthToken);
            var lines = new List<string>
            {
                "BlankTemplatePath=" + GetPathForConfig(BlankTemplatePath),
                "REMOVE_MODIFIED_NOTES=" + (RemoveModifiedNotes ? "True" : "False"),
                "FILTER_ANY=" + (FilterAny ?? string.Empty),
                "BOMtemplate=" + GetPathForConfig(BomTemplatePath),
                "weblink=" + (WebLink ?? string.Empty),
                "BackendUrl=" + (BackendUrl ?? string.Empty),
                "AuthToken=" + (protectedToken ?? string.Empty),
                "BOM_Folder=" + GetPathForConfig(BomFolder),
                "deliverables_folder=" + GetPathForConfig(DeliverablesFolder),
                "DxfSheetNames=" + (DxfSheetNames ?? string.Empty),
                "NumberingSchemeId=" + (NumberingSchemeId ?? string.Empty),
                "NumberingContextDefaults=" + (NumberingContextDefaults ?? string.Empty),
                "PartNumberProperty=" + (PartNumberProperty ?? "PartNumber"),
                "RevisionProperty=" + (RevisionProperty ?? "Revision"),
                "DisplayCodeProperty=" + (DisplayCodeProperty ?? "DisplayCode"),
                "NumberingApplyMode=" + (NumberingApplyMode ?? "active_config"),
                "AutoAssignGenericNames=" + (AutoAssignGenericNames ? "True" : "False"),
                "AutoAssignAnyNames=" + (AutoAssignAnyNames ? "True" : "False"),
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

        private string GetMachineConfigPath()
        {
            string baseDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
                "TinyMRP");
            return Path.Combine(baseDir, "TinyMRP_config.txt");
        }

        private static string SelectConfigPath(string machinePath, string addinPath, string userPath)
        {
            bool machineExists = File.Exists(machinePath);
            bool userExists = File.Exists(userPath);
            bool addinExists = File.Exists(addinPath);

            if (machineExists)
            {
                if (CanWriteToPath(machinePath) || !userExists)
                {
                    return machinePath;
                }
            }

            if (addinExists)
            {
                if (CanWriteToPath(addinPath) || !userExists)
                {
                    return addinPath;
                }
            }

            if (userExists)
            {
                return userPath;
            }

            return machinePath;
        }

        private static bool CanWriteToPath(string path)
        {
            try
            {
                if (File.Exists(path))
                {
                    using (new FileStream(path, FileMode.Open, FileAccess.Write, FileShare.Read))
                    {
                    }
                    return true;
                }

                string dir = Path.GetDirectoryName(path);
                return CanWriteToDirectory(dir);
            }
            catch
            {
                return false;
            }
        }

        private static bool CanWriteToDirectory(string dir)
        {
            if (string.IsNullOrWhiteSpace(dir))
            {
                return false;
            }

            try
            {
                Directory.CreateDirectory(dir);
                string probe = Path.Combine(dir, ".tinymrp_write_test");
                using (new FileStream(probe, FileMode.Create, FileAccess.Write, FileShare.None))
                {
                }
                File.Delete(probe);
                return true;
            }
            catch
            {
                return false;
            }
        }

        private string ProtectToken(string token)
        {
            if (string.IsNullOrWhiteSpace(token))
            {
                return string.Empty;
            }

            try
            {
                byte[] bytes = Encoding.UTF8.GetBytes(token);
                byte[] protectedBytes = ProtectedData.Protect(bytes, null, DataProtectionScope.CurrentUser);
                return "enc:" + Convert.ToBase64String(protectedBytes);
            }
            catch
            {
                return token;
            }
        }

        private string UnprotectToken(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                return string.Empty;
            }

            if (!value.StartsWith("enc:", StringComparison.OrdinalIgnoreCase))
            {
                return value;
            }

            try
            {
                string payload = value.Substring(4);
                byte[] data = Convert.FromBase64String(payload);
                byte[] unprotected = ProtectedData.Unprotect(data, null, DataProtectionScope.CurrentUser);
                return Encoding.UTF8.GetString(unprotected);
            }
            catch
            {
                return string.Empty;
            }
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
