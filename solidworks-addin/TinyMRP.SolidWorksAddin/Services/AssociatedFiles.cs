using System;
using System.Collections;
using System.Collections.Generic;
using System.Web.Script.Serialization;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal sealed class AssociatedFileEntry
    {
        public string Path { get; set; }
        public string Label { get; set; }
    }

    internal sealed class AssociatedFilesPayload
    {
        public const string PropertyName = "TINYMPR_ASSOC_FILES";

        public string PartNumber { get; set; }
        public string Revision { get; set; }
        public List<AssociatedFileEntry> Files { get; set; } = new List<AssociatedFileEntry>();

        public string ToJson()
        {
            var serializer = new JavaScriptSerializer();
            var data = new Dictionary<string, object>
            {
                ["pn"] = PartNumber ?? string.Empty,
                ["rev"] = Revision ?? string.Empty,
                ["files"] = BuildFileList()
            };
            return serializer.Serialize(data);
        }

        public static AssociatedFilesPayload FromJson(string json)
        {
            var payload = new AssociatedFilesPayload();
            if (string.IsNullOrWhiteSpace(json))
            {
                return payload;
            }

            try
            {
                var serializer = new JavaScriptSerializer();
                var data = serializer.DeserializeObject(json) as Dictionary<string, object>;
                if (data == null)
                {
                    return payload;
                }

                payload.PartNumber = ReadString(data, "pn");
                payload.Revision = ReadString(data, "rev");
                payload.Files = ReadFiles(data);
            }
            catch
            {
                return payload;
            }

            return payload;
        }

        private static string ReadString(Dictionary<string, object> data, string key)
        {
            if (data != null && data.TryGetValue(key, out object value) && value != null)
            {
                return value.ToString();
            }
            return string.Empty;
        }

        private static List<AssociatedFileEntry> ReadFiles(Dictionary<string, object> data)
        {
            var files = new List<AssociatedFileEntry>();
            if (data == null || !data.TryGetValue("files", out object raw) || raw == null)
            {
                return files;
            }

            IEnumerable items = raw as IEnumerable;
            if (items == null)
            {
                return files;
            }

            foreach (object item in items)
            {
                var dict = item as Dictionary<string, object>;
                if (dict == null)
                {
                    continue;
                }

                string path = ReadString(dict, "path");
                if (string.IsNullOrWhiteSpace(path))
                {
                    continue;
                }

                files.Add(new AssociatedFileEntry
                {
                    Path = path,
                    Label = ReadString(dict, "label")
                });
            }

            return files;
        }

        private List<Dictionary<string, object>> BuildFileList()
        {
            var list = new List<Dictionary<string, object>>();
            if (Files == null)
            {
                return list;
            }

            foreach (AssociatedFileEntry entry in Files)
            {
                if (entry == null || string.IsNullOrWhiteSpace(entry.Path))
                {
                    continue;
                }

                list.Add(new Dictionary<string, object>
                {
                    ["path"] = entry.Path ?? string.Empty,
                    ["label"] = entry.Label ?? string.Empty
                });
            }
            return list;
        }
    }
}
