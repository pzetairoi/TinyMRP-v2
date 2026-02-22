using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Microsoft.Win32;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swpublished;

namespace TinyMRP.SolidWorksAddin
{
    [ComVisible(true)]
    [Guid("D2A7E2A8-54D3-4E39-9E7B-3F35D0A7F3E6")]
    [ProgId("TinyMRP.SolidWorksAddin.Addin")]
    public class SwAddin : ISwAddin
    {
        private const string AddinTitle = "TinyMRP";
        private const string AddinDescription = "TinyMRP SolidWorks add-in";
        private const string TaskPaneTitle = "TinyMRP";
        private const string TaskPaneIconFileName = "TinyMRP.TaskPane.bmp";
        private const string AddinIconFileName = "TinyMRP.AddinIcon.bmp";
        private const string LogoRelativePath = "Assets\\logo.png";
        private const int TaskPaneIconSize = 20;
        private const int AddinIconSize = 16;

        private ISldWorks _swApp;
        private TaskpaneView _taskPane;
        private object _paneControl;
        private int _addinId;
        private string _taskPaneIconPath;

        private static string AddinTitleWithVersion()
        {
            return TitleWithVersion(AddinTitle, Assembly.GetExecutingAssembly());
        }

        private static string TaskPaneTitleWithVersion()
        {
            return TitleWithVersion(TaskPaneTitle, Assembly.GetExecutingAssembly());
        }

        private static string TitleWithVersion(string baseTitle, Assembly asm)
        {
            string version = string.Empty;
            try
            {
                if (asm != null && !string.IsNullOrWhiteSpace(asm.Location))
                {
                    version = FileVersionInfo.GetVersionInfo(asm.Location)?.FileVersion ?? string.Empty;
                }
            }
            catch
            {
                version = string.Empty;
            }

            if (string.IsNullOrWhiteSpace(version))
            {
                try
                {
                    version = (asm != null ? (asm.GetName().Version?.ToString() ?? string.Empty) : string.Empty);
                }
                catch
                {
                    version = string.Empty;
                }
            }

            if (string.IsNullOrWhiteSpace(version))
            {
                return baseTitle;
            }

            return baseTitle + " v" + version;
        }

        public bool ConnectToSW(object ThisSW, int cookie)
        {
            _swApp = (ISldWorks)ThisSW;
            _addinId = cookie;
            _swApp.SetAddinCallbackInfo2(0, this, _addinId);
            AddinContext.Initialize(_swApp);

            try
            {
                _taskPane = _swApp.CreateTaskpaneView2(GetTaskPaneIconPath(), TaskPaneTitleWithVersion());
                if (_taskPane != null)
                {
                    var paneObject = _taskPane.AddControl(UI.MainPaneControl.TaskPaneProgId, string.Empty);
                    if (paneObject == null)
                    {
                        MessageBox.Show("No se pudo cargar el control del panel. Verifica el registro COM del add-in.",
                            "TinyMRP", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    }
                    _paneControl = paneObject;
                    _taskPane.ShowView();
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("No se pudo crear el panel de TinyMRP: " + ex.Message, "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }

            return true;
        }

        public bool DisconnectFromSW()
        {
            try
            {
                if (_taskPane != null)
                {
                    _taskPane.DeleteView();
                }
            }
            catch
            {
                // ignore cleanup errors
            }

            _paneControl = null;
            _taskPane = null;
            _swApp = null;
            AddinContext.Clear();
            return true;
        }

        private string GetTaskPaneIconPath()
        {
            if (!string.IsNullOrWhiteSpace(_taskPaneIconPath) &&
                IsValidIcon(_taskPaneIconPath, TaskPaneIconSize))
            {
                return _taskPaneIconPath;
            }

            string addinDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string sourceLogo = Path.Combine(addinDir ?? string.Empty, LogoRelativePath);
            var dir = Path.Combine(System.Environment.GetFolderPath(System.Environment.SpecialFolder.LocalApplicationData), "TinyMRP");
            Directory.CreateDirectory(dir);
            _taskPaneIconPath = Path.Combine(dir, TaskPaneIconFileName);

            EnsureIcon(_taskPaneIconPath, sourceLogo, TaskPaneIconSize, "T");

            return _taskPaneIconPath;
        }

        private static void EnsureIcon(string outputPath, string sourceLogoPath, int size, string fallbackText)
        {
            if (IsValidIcon(outputPath, size))
            {
                return;
            }

            if (TryCreateIconFromLogo(outputPath, sourceLogoPath, size))
            {
                return;
            }

            CreateFallbackIcon(outputPath, fallbackText, size);
        }

        [ComRegisterFunction]
        public static void Register(Type t)
        {
            try
            {
                var keyPath = $"SOFTWARE\\SolidWorks\\AddIns\\{{{t.GUID}}}";
                var startupKeyPath = $"SOFTWARE\\SolidWorks\\AddInsStartup\\{{{t.GUID}}}";
                string addinDir = Path.GetDirectoryName(t.Assembly.Location);
                string logoPath = Path.Combine(addinDir ?? string.Empty, LogoRelativePath);
                string addinIconPath = Path.Combine(addinDir ?? string.Empty, AddinIconFileName);

                EnsureIcon(addinIconPath, logoPath, AddinIconSize, "T");
                using (var rk = Registry.LocalMachine.CreateSubKey(keyPath))
                {
                    if (rk != null)
                    {
                        rk.SetValue(null, 1);
                        rk.SetValue("Title", TitleWithVersion(AddinTitle, t.Assembly));
                        rk.SetValue("Description", AddinDescription);
                        if (File.Exists(addinIconPath))
                        {
                            rk.SetValue("Icon", addinIconPath);
                        }
                    }
                }

                using (var userKey = Registry.CurrentUser.CreateSubKey(keyPath))
                {
                    if (userKey != null)
                    {
                        userKey.SetValue(null, 1);
                    }
                }

                using (var startupKey = Registry.CurrentUser.CreateSubKey(startupKeyPath))
                {
                    if (startupKey != null)
                    {
                        startupKey.SetValue(null, 1);
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("Error registrando el add-in: " + ex.Message);
            }
        }

        [ComUnregisterFunction]
        public static void Unregister(Type t)
        {
            try
            {
                var keyPath = $"SOFTWARE\\SolidWorks\\AddIns\\{{{t.GUID}}}";
                var startupKeyPath = $"SOFTWARE\\SolidWorks\\AddInsStartup\\{{{t.GUID}}}";
                Registry.LocalMachine.DeleteSubKeyTree(keyPath, false);
                Registry.CurrentUser.DeleteSubKeyTree(keyPath, false);
                Registry.CurrentUser.DeleteSubKeyTree(startupKeyPath, false);
            }
            catch
            {
                // ignore unregister errors
            }
        }

        private static bool TryCreateIconFromLogo(string outputPath, string logoPath, int size)
        {
            try
            {
                if (string.IsNullOrWhiteSpace(logoPath) || !File.Exists(logoPath))
                {
                    return false;
                }

                using (var source = (Bitmap)Image.FromFile(logoPath))
                using (var bmp = new Bitmap(size, size, PixelFormat.Format24bppRgb))
                using (var g = Graphics.FromImage(bmp))
                {
                    g.Clear(Color.White);
                    g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                    g.DrawImage(source, new Rectangle(0, 0, size, size));
                    bmp.Save(outputPath, ImageFormat.Bmp);
                }

                return File.Exists(outputPath);
            }
            catch
            {
                return false;
            }
        }

        private static void CreateFallbackIcon(string outputPath, string text, int size)
        {
            try
            {
                using (var bmp = new Bitmap(size, size, PixelFormat.Format24bppRgb))
                using (var g = Graphics.FromImage(bmp))
                using (var bg = new SolidBrush(Color.FromArgb(21, 92, 141)))
                using (var fg = new SolidBrush(Color.White))
                using (var font = new Font("Segoe UI", size > 16 ? 12 : 9, FontStyle.Bold, GraphicsUnit.Pixel))
                {
                    g.Clear(Color.White);
                    g.FillRectangle(bg, 0, 0, size, size);
                    g.DrawString(text ?? "T", font, fg, new PointF(size * 0.28f, size * 0.2f));
                    bmp.Save(outputPath, ImageFormat.Bmp);
                }
            }
            catch
            {
                // ignore icon generation errors
            }
        }

        private static bool IsValidIcon(string path, int size)
        {
            try
            {
                if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
                {
                    return false;
                }

                using (var bmp = new Bitmap(path))
                {
                    return bmp.Width == size && bmp.Height == size;
                }
            }
            catch
            {
                return false;
            }
        }
    }
}
