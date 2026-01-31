using System;
using System.IO;
using System.Text;

namespace TinyMRP.SolidWorksAddin.Services
{
    internal static class TextFileHelper
    {
        internal static readonly Encoding Utf8NoBom =
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);

        public static StreamWriter CreateUtf8NoBomWriter(string path)
        {
            return new StreamWriter(path, false, Utf8NoBom);
        }

        public static void WriteAllTextUtf8NoBom(string path, string content)
        {
            File.WriteAllText(path, content ?? string.Empty, Utf8NoBom);
        }

        public static bool StripUtf8Bom(string path)
        {
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                return false;
            }

            byte[] bytes = File.ReadAllBytes(path);
            if (bytes.Length < 3)
            {
                return false;
            }

            if (bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF)
            {
                byte[] trimmed = new byte[bytes.Length - 3];
                Buffer.BlockCopy(bytes, 3, trimmed, 0, trimmed.Length);
                File.WriteAllBytes(path, trimmed);
                return true;
            }

            return false;
        }

        public static bool HasUtf8Bom(string path)
        {
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                return false;
            }

            byte[] bytes = File.ReadAllBytes(path);
            return bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF;
        }
    }
}
