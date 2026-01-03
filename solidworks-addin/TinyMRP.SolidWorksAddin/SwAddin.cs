using System;
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

        private ISldWorks _swApp;
        private TaskpaneView _taskPane;
        private object _paneControl;
        private int _addinId;
        private string _taskPaneIconPath;

        public bool ConnectToSW(object ThisSW, int cookie)
        {
            _swApp = (ISldWorks)ThisSW;
            _addinId = cookie;
            _swApp.SetAddinCallbackInfo2(0, this, _addinId);
            AddinContext.Initialize(_swApp);

            try
            {
                _taskPane = _swApp.CreateTaskpaneView2(GetTaskPaneIconPath(), TaskPaneTitle);
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
            if (!string.IsNullOrWhiteSpace(_taskPaneIconPath) && File.Exists(_taskPaneIconPath))
            {
                return _taskPaneIconPath;
            }

            string addinDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string sourceLogo = Path.Combine(addinDir ?? string.Empty, LogoRelativePath);
            var dir = Path.Combine(System.Environment.GetFolderPath(System.Environment.SpecialFolder.LocalApplicationData), "TinyMRP");
            Directory.CreateDirectory(dir);
            _taskPaneIconPath = Path.Combine(dir, TaskPaneIconFileName);

            if (!File.Exists(_taskPaneIconPath))
            {
                CreateTaskPaneIcon(_taskPaneIconPath, sourceLogo);
            }

            return _taskPaneIconPath;
        }

        private static void CreateTaskPaneIcon(string path, string sourceLogoPath)
        {
            if (TryCreateIconFromLogo(path, sourceLogoPath))
            {
                return;
            }

            CreateFallbackIcon(path, "T");
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

                if (!File.Exists(addinIconPath))
                {
                    if (!TryCreateIconFromLogo(addinIconPath, logoPath))
                    {
                        CreateFallbackIcon(addinIconPath, "T");
                    }
                }
                using (var rk = Registry.LocalMachine.CreateSubKey(keyPath))
                {
                    if (rk != null)
                    {
                        rk.SetValue(null, 1);
                        rk.SetValue("Title", AddinTitle);
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

        private static bool TryCreateIconFromLogo(string outputPath, string logoPath)
        {
            try
            {
                if (string.IsNullOrWhiteSpace(logoPath) || !File.Exists(logoPath))
                {
                    return false;
                }

                using (var source = (Bitmap)Image.FromFile(logoPath))
                using (var bmp = new Bitmap(32, 32))
                using (var g = Graphics.FromImage(bmp))
                {
                    g.Clear(Color.White);
                    g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                    g.DrawImage(source, new Rectangle(0, 0, 32, 32));
                    bmp.Save(outputPath, ImageFormat.Bmp);
                }

                return File.Exists(outputPath);
            }
            catch
            {
                return false;
            }
        }

        private static void CreateFallbackIcon(string outputPath, string text)
        {
            try
            {
                using (var bmp = new Bitmap(32, 32))
                using (var g = Graphics.FromImage(bmp))
                using (var bg = new SolidBrush(Color.FromArgb(21, 92, 141)))
                using (var fg = new SolidBrush(Color.White))
                using (var font = new Font("Segoe UI", 12, FontStyle.Bold, GraphicsUnit.Pixel))
                {
                    g.Clear(Color.White);
                    g.FillRectangle(bg, 0, 0, 32, 32);
                    g.DrawString(text ?? "T", font, fg, new PointF(9, 6));
                    bmp.Save(outputPath, ImageFormat.Bmp);
                }
            }
            catch
            {
                // ignore icon generation errors
            }
        }
    }
}
