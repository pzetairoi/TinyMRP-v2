using System;
using System.IO;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal static class AddinLogger
    {
        private static readonly object _lock = new object();

        public static string LogPath
        {
            get
            {
                string dir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "TinyMRP",
                    "logs");
                return Path.Combine(dir, "addin.log");
            }
        }

        public static void Write(string message)
        {
            if (string.IsNullOrWhiteSpace(message))
            {
                return;
            }

            try
            {
                string path = LogPath;
                string dir = Path.GetDirectoryName(path);
                if (!string.IsNullOrWhiteSpace(dir))
                {
                    Directory.CreateDirectory(dir);
                }

                string line = DateTime.UtcNow.ToString("s") + " " + message + Environment.NewLine;
                lock (_lock)
                {
                    File.AppendAllText(path, line);
                }
            }
            catch
            {
                // Ignore logging failures.
            }
        }
    }
}
