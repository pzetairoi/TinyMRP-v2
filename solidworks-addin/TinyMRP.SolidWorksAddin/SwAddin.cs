using System;
using System.Configuration;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Microsoft.Win32;
using SolidWorks.Interop.sldworks;
using TinyMRP.SolidWorksAddin.Services;

namespace TinyMRP.SolidWorksAddin
{
    [ComVisible(true)]
    [Guid("3C0CB70A-FFDA-4CCB-8B9D-55EA0C2D6536")]
    [ProgId("TinyMRP.SolidWorksAddin.Addin")]
    public class SwAddin : ISwAddin
    {
        private ISldWorks? _swApp;
        private int _addinId;
        private TaskpaneView? _taskPane;
        private UI.MainPaneControl? _paneControl;
        private SolidWorksExportService? _exporter;
        private TinyMrpClient? _client;

        public bool ConnectToSW(object ThisSW, int cookie)
        {
            _swApp = (ISldWorks)ThisSW;
            _addinId = cookie;
            _exporter = new SolidWorksExportService(_swApp);
            _client = BuildClient();

            try
            {
                _taskPane = _swApp.CreateTaskpaneView2(string.Empty, "TinyMRP");
                var ctrl = _taskPane?.AddControl("TinyMRP.SolidWorksAddin.UI.MainPaneControl", "TinyMRP") as UI.MainPaneControl;
                _paneControl = ctrl;
                _paneControl?.Initialize(_client, _exporter, _swApp);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"No se pudo crear el panel de TinyMRP: {ex.Message}", "TinyMRP", MessageBoxButtons.OK, MessageBoxIcon.Error);
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
            _exporter = null;
            _client = null;
            return true;
        }

        private TinyMrpClient BuildClient()
        {
            var baseUrl = ConfigurationManager.AppSettings["TinyMrpBaseUrl"] ?? "http://localhost:5000";
            var filesRoot = ConfigurationManager.AppSettings["FilesLocalRoot"] ?? string.Empty;
            var filesUrl = ConfigurationManager.AppSettings["FilesUrlPrefix"] ?? string.Empty;
            var reserveEndpoint = ConfigurationManager.AppSettings["ReservePnEndpoint"] ?? "/api/pn/reserve";
            var store = new TinyMrpTokenStore();

            if (!string.IsNullOrWhiteSpace(store.BaseUrl))
            {
                baseUrl = store.BaseUrl;
            }
            if (!string.IsNullOrWhiteSpace(store.FilesLocalRoot))
            {
                filesRoot = store.FilesLocalRoot;
            }
            if (!string.IsNullOrWhiteSpace(store.FilesUrlPrefix))
            {
                filesUrl = store.FilesUrlPrefix;
            }

            return new TinyMrpClient(new Uri(baseUrl), filesRoot, filesUrl, reserveEndpoint, store);
        }

        [ComRegisterFunction]
        public static void Register(Type t)
        {
            try
            {
                var keyPath = $"SOFTWARE\\SolidWorks\\AddIns\\{{{t.GUID}}}";
                using var rk = Registry.LocalMachine.CreateSubKey(keyPath);
                rk?.SetValue(null, 1);
                rk?.SetValue("Title", "TinyMRP Add-in");
                rk?.SetValue("Description", "Generación de packs TinyMRP desde SolidWorks");

                using var userKey = Registry.CurrentUser.CreateSubKey(keyPath);
                userKey?.SetValue(null, 1);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error registrando el add-in: {ex.Message}");
            }
        }

        [ComUnregisterFunction]
        public static void Unregister(Type t)
        {
            try
            {
                var keyPath = $"SOFTWARE\\SolidWorks\\AddIns\\{{{t.GUID}}}";
                Registry.LocalMachine.DeleteSubKeyTree(keyPath, false);
                Registry.CurrentUser.DeleteSubKeyTree(keyPath, false);
            }
            catch
            {
                // ignore unregister errors
            }
        }
    }
}
