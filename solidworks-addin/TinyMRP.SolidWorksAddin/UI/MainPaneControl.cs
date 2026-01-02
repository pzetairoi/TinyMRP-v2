using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows.Forms;
using SolidWorks.Interop.sldworks;
using TinyMRP.SolidWorksAddin.Models;
using TinyMRP.SolidWorksAddin.Services;

namespace TinyMRP.SolidWorksAddin.UI
{
    [ComVisible(true)]
    [ProgId("TinyMRP.SolidWorksAddin.UI.MainPaneControl")]
    public class MainPaneControl : UserControl
    {
        private TinyMrpClient? _client;
        private SolidWorksExportService? _exporter;
        private ISldWorks? _swApp;

        private TextBox txtBaseUrl = new();
        private TextBox txtFilesRoot = new();
        private TextBox txtFilesUrl = new();
        private TextBox txtEmail = new();
        private TextBox txtPassword = new() { UseSystemPasswordChar = true };
        private Label lblStatus = new() { AutoSize = true, ForeColor = Color.Teal };
        private TextBox txtPn = new();
        private TextBox txtRev = new();
        private CheckedListBox lstFileTypes = new() { CheckOnClick = true, Height = 90 };
        private CheckedListBox lstProcesses = new() { CheckOnClick = true, Height = 90 };
        private CheckBox chkTopLevel = new() { Text = "Top level only" };
        private CheckBox chkOverwrite = new() { Text = "Overwrite" };
        private CheckBox chkExcel = new() { Text = "Excel BOM", Checked = true };
        private CheckBox chkBinder = new() { Text = "PDF binder" };
        private CheckBox chkVisual = new() { Text = "Visual list" };
        private CheckBox chkSelected = new() { Text = "Selected files" };
        private CheckBox chkFabPack = new() { Text = "Fabrication pack" };
        private CheckBox chkIncludeConsumed = new() { Text = "Include consumed" };
        private CheckBox chkBinderIndex = new() { Text = "Binder index" };
        private CheckBox chkBinderDatasheets = new() { Text = "Datasheets" };
        private CheckBox chkBinderPages = new() { Text = "Page numbers", Checked = true };
        private CheckBox chkStampQuote = new() { Text = "Quote" };
        private CheckBox chkStampConf = new() { Text = "Confidential" };
        private CheckBox chkStampApproved = new() { Text = "Approved" };
        private CheckBox chkStampWip = new() { Text = "WIP" };
        private CheckBox chkStampProgress = new() { Text = "In progress" };
        private ListBox lstModels = new();
        private ListBox lstDrawings = new();
        private ListView lvLog = new() { View = View.Details, FullRowSelect = true, Height = 120, Dock = DockStyle.Fill };
        private Button btnLogin = new() { Text = "Login" };
        private Button btnRefreshOptions = new() { Text = "Cargar tipos" };
        private Button btnReservePn = new() { Text = "Reservar PN" };
        private Button btnBom = new() { Text = "BOM" };
        private Button btnFreeze = new() { Text = "Freeze" };
        private Button btnUnfreeze = new() { Text = "Unfreeze" };

        public MainPaneControl()
        {
            Dock = DockStyle.Fill;
            AutoScroll = true;
            BuildLayout();
        }

        public void Initialize(TinyMrpClient client, SolidWorksExportService exporter, ISldWorks swApp)
        {
            _client = client;
            _exporter = exporter;
            _swApp = swApp;
            LoadState();
        }

        private void BuildLayout()
        {
            var root = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 1,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Padding = new Padding(6),
            };

            root.Controls.Add(BuildAuthPanel());
            root.Controls.Add(BuildPnPanel());
            root.Controls.Add(BuildListPanel());
            root.Controls.Add(BuildDocPackPanel());
            root.Controls.Add(BuildButtonsPanel());
            root.Controls.Add(BuildLogPanel());

            Controls.Add(root);
        }

        private Control BuildAuthPanel()
        {
            var gb = new GroupBox { Text = "TinyMRP", Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Padding = new Padding(8) };
            var layout = new TableLayoutPanel { ColumnCount = 2, Dock = DockStyle.Fill, AutoSize = true };
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 30));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 70));

            layout.Controls.Add(new Label { Text = "Base URL", AutoSize = true }, 0, 0);
            layout.Controls.Add(txtBaseUrl, 1, 0);
            layout.Controls.Add(new Label { Text = "FILES_LOCAL_ROOT", AutoSize = true }, 0, 1);
            layout.Controls.Add(txtFilesRoot, 1, 1);
            layout.Controls.Add(new Label { Text = "FILES_URL_PREFIX", AutoSize = true }, 0, 2);
            layout.Controls.Add(txtFilesUrl, 1, 2);
            layout.Controls.Add(new Label { Text = "Email", AutoSize = true }, 0, 3);
            layout.Controls.Add(txtEmail, 1, 3);
            layout.Controls.Add(new Label { Text = "Password", AutoSize = true }, 0, 4);
            layout.Controls.Add(txtPassword, 1, 4);
            layout.Controls.Add(btnLogin, 1, 5);
            layout.Controls.Add(lblStatus, 1, 6);

            btnLogin.Click += async (_, __) => await LoginAsync();

            gb.Controls.Add(layout);
            return gb;
        }

        private Control BuildPnPanel()
        {
            var gb = new GroupBox { Text = "MODELS / DRAWINGS", Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Padding = new Padding(8) };
            var layout = new TableLayoutPanel { ColumnCount = 4, Dock = DockStyle.Fill, AutoSize = true };
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25));

            layout.Controls.Add(new Label { Text = "PN", AutoSize = true }, 0, 0);
            layout.Controls.Add(txtPn, 1, 0);
            layout.Controls.Add(new Label { Text = "REV", AutoSize = true }, 2, 0);
            layout.Controls.Add(txtRev, 3, 0);

            layout.Controls.Add(new Label { Text = "MODELS", AutoSize = true }, 0, 1);
            layout.Controls.Add(new Label { Text = "DRAWINGS", AutoSize = true }, 2, 1);

            lstModels.Height = 90;
            lstDrawings.Height = 90;
            layout.Controls.Add(lstModels, 0, 2);
            layout.SetColumnSpan(lstModels, 2);
            layout.Controls.Add(lstDrawings, 2, 2);
            layout.SetColumnSpan(lstDrawings, 2);

            var btnAddModel = new Button { Text = "Add active", AutoSize = true };
            btnAddModel.Click += (_, __) => AddActiveToList(lstModels);
            var btnAddDrawing = new Button { Text = "Add active", AutoSize = true };
            btnAddDrawing.Click += (_, __) => AddActiveToList(lstDrawings);
            var btnRemoveModel = new Button { Text = "Remove", AutoSize = true };
            btnRemoveModel.Click += (_, __) => RemoveSelected(lstModels);
            var btnRemoveDrawing = new Button { Text = "Remove", AutoSize = true };
            btnRemoveDrawing.Click += (_, __) => RemoveSelected(lstDrawings);

            layout.Controls.Add(btnAddModel, 0, 3);
            layout.Controls.Add(btnRemoveModel, 1, 3);
            layout.Controls.Add(btnAddDrawing, 2, 3);
            layout.Controls.Add(btnRemoveDrawing, 3, 3);

            gb.Controls.Add(layout);
            return gb;
        }

        private Control BuildListPanel()
        {
            var gb = new GroupBox { Text = "Salida", Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Padding = new Padding(8) };
            var layout = new FlowLayoutPanel { FlowDirection = FlowDirection.LeftToRight, Dock = DockStyle.Fill, AutoSize = true, WrapContents = true };
            layout.Controls.Add(chkOverwrite);
            layout.Controls.Add(chkTopLevel);
            layout.Controls.Add(chkIncludeConsumed);
            var btnOpen = new Button { Text = "Abrir carpeta", AutoSize = true };
            btnOpen.Click += (_, __) => OpenFolder(txtFilesRoot.Text.Trim());
            layout.Controls.Add(btnOpen);
            gb.Controls.Add(layout);
            return gb;
        }

        private Control BuildDocPackPanel()
        {
            var gb = new GroupBox { Text = "DocPack", Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Padding = new Padding(8) };
            var layout = new TableLayoutPanel { ColumnCount = 2, Dock = DockStyle.Fill, AutoSize = true };
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));

            layout.Controls.Add(new Label { Text = "Tipos de archivo", AutoSize = true }, 0, 0);
            layout.Controls.Add(new Label { Text = "Procesos", AutoSize = true }, 1, 0);
            layout.Controls.Add(lstFileTypes, 0, 1);
            layout.Controls.Add(lstProcesses, 1, 1);

            var optionsPanel = new FlowLayoutPanel { FlowDirection = FlowDirection.LeftToRight, AutoSize = true, WrapContents = true };
            optionsPanel.Controls.Add(chkExcel);
            optionsPanel.Controls.Add(chkBinder);
            optionsPanel.Controls.Add(chkVisual);
            optionsPanel.Controls.Add(chkSelected);
            optionsPanel.Controls.Add(chkFabPack);
            optionsPanel.Controls.Add(chkBinderIndex);
            optionsPanel.Controls.Add(chkBinderDatasheets);
            optionsPanel.Controls.Add(chkBinderPages);
            optionsPanel.Controls.Add(chkStampQuote);
            optionsPanel.Controls.Add(chkStampConf);
            optionsPanel.Controls.Add(chkStampApproved);
            optionsPanel.Controls.Add(chkStampWip);
            optionsPanel.Controls.Add(chkStampProgress);

            layout.Controls.Add(optionsPanel, 0, 2);
            layout.SetColumnSpan(optionsPanel, 2);

            btnRefreshOptions.Click += async (_, __) => await RefreshOptionsAsync();
            btnReservePn.Click += async (_, __) => await ReservePnAsync();

            var actionPanel = new FlowLayoutPanel { FlowDirection = FlowDirection.LeftToRight, AutoSize = true };
            actionPanel.Controls.Add(btnRefreshOptions);
            actionPanel.Controls.Add(btnReservePn);
            layout.Controls.Add(actionPanel, 0, 3);
            layout.SetColumnSpan(actionPanel, 2);

            gb.Controls.Add(layout);
            return gb;
        }

        private Control BuildButtonsPanel()
        {
            var panel = new FlowLayoutPanel { FlowDirection = FlowDirection.LeftToRight, Dock = DockStyle.Top, AutoSize = true, Padding = new Padding(4) };
            btnBom.Click += async (_, __) => await RunDocPackAsync();
            btnFreeze.Click += (_, __) => DoFreeze(true);
            btnUnfreeze.Click += (_, __) => DoFreeze(false);
            panel.Controls.Add(btnBom);
            panel.Controls.Add(btnFreeze);
            panel.Controls.Add(btnUnfreeze);
            return panel;
        }

        private Control BuildLogPanel()
        {
            lvLog.Columns.Add("Acción", 140);
            lvLog.Columns.Add("Detalle", 320);
            lvLog.MultiSelect = false;
            lvLog.DoubleClick += (s, e) => OpenSelectedLog();

            var panel = new GroupBox { Text = "Eventos", Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Padding = new Padding(6) };
            panel.Controls.Add(lvLog);
            return panel;
        }

        private async Task LoginAsync()
        {
            if (_client == null)
            {
                return;
            }

            try
            {
                lblStatus.Text = "Autenticando...";
                var result = await _client.LoginAsync(txtEmail.Text.Trim(), txtPassword.Text, default);
                lblStatus.Text = result.Message;
                _client.PersistSettings(txtFilesRoot.Text.Trim(), txtFilesUrl.Text.Trim());
            }
            catch (Exception ex)
            {
                lblStatus.Text = ex.Message;
            }
        }

        private async Task RefreshOptionsAsync()
        {
            if (_client == null)
            {
                return;
            }

            try
            {
                lblStatus.Text = "Cargando opciones...";
                var opts = await _client.GetOptionsAsync(txtPn.Text.Trim(), txtRev.Text.Trim(), chkTopLevel.Checked, default);
                lstFileTypes.Items.Clear();
                lstProcesses.Items.Clear();
                if (opts != null)
                {
                    foreach (var t in opts.FileTypes)
                    {
                        lstFileTypes.Items.Add(t, true);
                    }
                    foreach (var p in opts.Processes)
                    {
                        lstProcesses.Items.Add(p, false);
                    }
                }
                lblStatus.Text = "Opciones actualizadas";
            }
            catch (Exception ex)
            {
                lblStatus.Text = ex.Message;
            }
        }

        private async Task ReservePnAsync()
        {
            if (_client == null || _exporter == null)
            {
                return;
            }

            try
            {
                lblStatus.Text = "Reservando PN...";
                var response = await _client.ReservePnAsync(txtPn.Text.Trim());
                if (response?.PartNumber != null)
                {
                    txtPn.Text = response.PartNumber;
                }
                if (!string.IsNullOrWhiteSpace(response?.Revision))
                {
                    txtRev.Text = response.Revision;
                }
                _exporter.ApplyReservedPn(_exporter.ActiveDocument, txtPn.Text.Trim(), string.IsNullOrWhiteSpace(txtRev.Text) ? null : txtRev.Text.Trim(), true);
                lblStatus.Text = response?.Message ?? "PN reservado y aplicado";
                AppendLog("PN", $"Asignado {txtPn.Text} / {txtRev.Text}");
            }
            catch (Exception ex)
            {
                lblStatus.Text = ex.Message;
            }
        }

        private async Task RunDocPackAsync()
        {
            if (_client == null)
            {
                return;
            }

            var pn = txtPn.Text.Trim();
            if (string.IsNullOrWhiteSpace(pn))
            {
                lblStatus.Text = "PN requerido";
                return;
            }

            try
            {
                lblStatus.Text = "Generando...";
                var req = BuildRequest();
                var result = await _client.BuildDocPackAsync(req, chkOverwrite.Checked, default);
                if (result == null)
                {
                    lblStatus.Text = "Falló la generación";
                    return;
                }

                lblStatus.Text = "Listo";
                AppendLog("DocPack", result.HttpUrl ?? result.LocalPath, result.LocalPath, result.HttpUrl);
            }
            catch (Exception ex)
            {
                lblStatus.Text = ex.Message;
            }
        }

        private DocPackRequest BuildRequest()
        {
            var processes = lstProcesses.CheckedItems.Cast<object>().Select(o => o.ToString() ?? string.Empty).Where(s => !string.IsNullOrWhiteSpace(s)).ToList();
            var files = lstFileTypes.CheckedItems.Cast<object>().Select(o => o.ToString() ?? string.Empty).Where(s => !string.IsNullOrWhiteSpace(s)).ToList();

            return new DocPackRequest
            {
                PartNumber = txtPn.Text.Trim(),
                Revision = string.IsNullOrWhiteSpace(txtRev.Text) ? null : txtRev.Text.Trim(),
                Depth = chkTopLevel.Checked ? "top" : "full",
                IncludeConsumed = chkIncludeConsumed.Checked,
                Classified = "show",
                ProcessMode = processes.Any() ? "selected" : "all",
                Processes = processes,
                FileTypes = files,
                ExcelBom = chkExcel.Checked,
                PdfBinder = chkBinder.Checked,
                VisualList = chkVisual.Checked,
                SelectedFiles = chkSelected.Checked,
                FabricationPack = chkFabPack.Checked,
                BinderAddIndex = chkBinderIndex.Checked,
                BinderAddDatasheets = chkBinderDatasheets.Checked,
                BinderPageNumbers = chkBinderPages.Checked,
                StampQuote = chkStampQuote.Checked,
                StampConfidential = chkStampConf.Checked,
                StampApproved = chkStampApproved.Checked,
                StampWip = chkStampWip.Checked,
                StampInProgress = chkStampProgress.Checked
            };
        }

        private void DoFreeze(bool freeze)
        {
            if (_exporter == null)
            {
                return;
            }

            var ok = freeze ? _exporter.Freeze(_exporter.ActiveDocument) : _exporter.Unfreeze(_exporter.ActiveDocument);
            AppendLog(freeze ? "Freeze" : "Unfreeze", ok ? "OK" : "Sin cambios");
        }

        private void AddActiveToList(ListBox list)
        {
            if (_exporter?.ActiveDocument == null)
            {
                return;
            }
            var doc = _exporter.ActiveDocument;
            var entry = string.IsNullOrWhiteSpace(doc.GetPathName()) ? doc.GetTitle() : doc.GetPathName();
            if (!string.IsNullOrWhiteSpace(entry) && !list.Items.Contains(entry))
            {
                list.Items.Add(entry);
            }
        }

        private static void RemoveSelected(ListBox list)
        {
            if (list.SelectedItem != null)
            {
                list.Items.Remove(list.SelectedItem);
            }
        }

        private void AppendLog(string action, string detail, string? path = null, string? url = null)
        {
            var item = new ListViewItem(action);
            item.SubItems.Add(detail);
            item.Tag = new LogData { Path = path, Url = url };
            lvLog.Items.Insert(0, item);
        }

        private void OpenSelectedLog()
        {
            if (lvLog.SelectedItems.Count == 0)
            {
                return;
            }

            if (lvLog.SelectedItems[0].Tag is LogData data)
            {
                var target = data.Path ?? data.Url;
                if (!string.IsNullOrWhiteSpace(target))
                {
                    try
                    {
                        System.Diagnostics.Process.Start(target);
                    }
                    catch
                    {
                        // ignore
                    }
                }
            }
        }

        private void LoadState()
        {
            txtBaseUrl.Text = _client?.BaseUri.ToString() ?? txtBaseUrl.Text;
            txtFilesRoot.Text = _client?.FilesLocalRoot ?? txtFilesRoot.Text;
            txtFilesUrl.Text = _client?.FilesUrlPrefix ?? txtFilesUrl.Text;
        }

        private void OpenFolder(string path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return;
            }
            try
            {
                if (!Directory.Exists(path))
                {
                    Directory.CreateDirectory(path);
                }
                Process.Start(path);
            }
            catch
            {
                // ignore errors when opening explorer
            }
        }

        private class LogData
        {
            public string? Path { get; set; }
            public string? Url { get; set; }
        }
    }
}
