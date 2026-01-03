using System;
using System.Diagnostics;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using TinyMRP.SolidWorksAddin;
using TinyMRP.SolidWorksAddin.Services;

namespace TinyMRP.SolidWorksAddin.UI
{
    [ComVisible(true)]
    [Guid("7F24E7B5-2E52-4E46-9B39-6E1C5A3E6D12")]
    [ProgId(TaskPaneProgId)]
    [ClassInterface(ClassInterfaceType.AutoDispatch)]
    public class MainPaneControl : UserControl
    {
        public const string TaskPaneProgId = "TinyMRP.SolidWorksAddin.UI.MainPaneControl";

        private readonly TabControl _tabs = new TabControl { Dock = DockStyle.Fill };

        private TextBox _deliverablesFolderText;
        private TextBox _bomFolderText;
        private TextBox _weblinkText;
        private TextBox _bomTemplateText;
        private TextBox _blankTemplateText;
        private CheckBox _removeModifiedNotesCheck;
        private CheckBox _topLevelOnlyCheck;
        private CheckBox _overwriteCheck;
        private CheckBox _pngModelCheck;
        private CheckBox _stepCheck;
        private CheckBox _edrCheck;
        private CheckBox _threeMfCheck;
        private CheckBox _pngDrawingCheck;
        private CheckBox _pdfCheck;
        private CheckBox _edrDrawingCheck;
        private TextBox _logBox;
        private Label _configPathLabel;

        public MainPaneControl()
        {
            Dock = DockStyle.Fill;
            BackColor = SystemColors.Control;
            AutoScroll = true;
            MinimumSize = new Size(280, 320);

            var header = new Label
            {
                Text = "TinyMRP",
                Font = new Font("Segoe UI", 11F, FontStyle.Bold, GraphicsUnit.Point),
                AutoSize = true,
                Padding = new Padding(4, 4, 4, 0)
            };

            var root = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 2,
                Padding = new Padding(6)
            };
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            root.RowStyles.Add(new RowStyle(SizeType.Percent, 100F));
            root.Controls.Add(header, 0, 0);
            root.Controls.Add(_tabs, 0, 1);

            Controls.Add(root);

            BuildTabs();
            ApplyConfig(AddinContext.Config);
        }

        private void BuildTabs()
        {
            _tabs.TabPages.Add(BuildPublishTab());
            _tabs.TabPages.Add(BuildBomTab());
            _tabs.TabPages.Add(BuildConfigTab());
        }

        private TabPage BuildPublishTab()
        {
            var page = CreateTabPage("Publish");
            var panel = CreateTabPanel();
            page.Controls.Add(panel);

            var modelChecks = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            _pngModelCheck = new CheckBox { Text = "PNG" };
            _stepCheck = new CheckBox { Text = "STEP" };
            _edrCheck = new CheckBox { Text = "eDrawings" };
            _threeMfCheck = new CheckBox { Text = "3MF" };
            modelChecks.Controls.Add(_pngModelCheck);
            modelChecks.Controls.Add(_stepCheck);
            modelChecks.Controls.Add(_edrCheck);
            modelChecks.Controls.Add(_threeMfCheck);

            var drawingChecks = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            _pngDrawingCheck = new CheckBox { Text = "PNG drawing" };
            _pdfCheck = new CheckBox { Text = "PDF" };
            _edrDrawingCheck = new CheckBox { Text = "eDrawings drawing" };
            drawingChecks.Controls.Add(_pngDrawingCheck);
            drawingChecks.Controls.Add(_pdfCheck);
            drawingChecks.Controls.Add(_edrDrawingCheck);

            var deliverablesLayout = new TableLayoutPanel
            {
                ColumnCount = 2,
                RowCount = 1,
                Dock = DockStyle.Fill,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink
            };
            deliverablesLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50F));
            deliverablesLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50F));
            deliverablesLayout.RowStyles.Add(new RowStyle(SizeType.AutoSize));

            var modelsBox = CreateGroupBox("Models", modelChecks);
            modelsBox.AutoSize = false;
            modelsBox.Dock = DockStyle.Fill;
            modelsBox.MinimumSize = new Size(160, 200);

            var drawingsBox = CreateGroupBox("Drawings", drawingChecks);
            drawingsBox.AutoSize = false;
            drawingsBox.Dock = DockStyle.Fill;
            drawingsBox.MinimumSize = new Size(160, 200);

            deliverablesLayout.Controls.Add(modelsBox, 0, 0);
            deliverablesLayout.Controls.Add(drawingsBox, 1, 0);
            deliverablesLayout.MinimumSize = new Size(0, 200);
            AddSection(panel, CreateGroupBox("Deliverables", deliverablesLayout));

            var optionsPanel = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
                Dock = DockStyle.Fill
            };
            _overwriteCheck = new CheckBox { Text = "Overwrite files" };
            _topLevelOnlyCheck = new CheckBox { Text = "Top level only" };
            optionsPanel.Controls.Add(_overwriteCheck);
            optionsPanel.Controls.Add(_topLevelOnlyCheck);
            AddSection(panel, CreateGroupBox("Options", optionsPanel));

            var paths = CreateFormLayout();
            _deliverablesFolderText = new TextBox { Width = 200 };
            AddField(paths, "Deliverables folder", CreateFolderPicker(_deliverablesFolderText, OnBrowseDeliverables));
            AddSection(panel, CreateGroupBox("Paths", paths));

            var actions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
                Dock = DockStyle.Fill
            };
            var btnSelectAll = new Button { Text = "Select all", AutoSize = true };
            btnSelectAll.Click += (_, __) => SetDeliverableChecks(true);
            var btnDeselectAll = new Button { Text = "Deselect", AutoSize = true };
            btnDeselectAll.Click += (_, __) => SetDeliverableChecks(false);
            var btnCreate = new Button { Text = "Create files", AutoSize = true };
            btnCreate.Click += OnCreateFiles;
            actions.Controls.Add(btnSelectAll);
            actions.Controls.Add(btnDeselectAll);
            actions.Controls.Add(btnCreate);
            AddSection(panel, CreateGroupBox("Actions", actions));

            _logBox = new TextBox
            {
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                Dock = DockStyle.Fill
            };
            _logBox.MinimumSize = new Size(0, 120);
            var logGroup = CreateGroupBox("Log", _logBox);
            logGroup.AutoSize = false;
            logGroup.Height = 170;
            AddSection(panel, logGroup);

            return page;
        }

        private TabPage BuildBomTab()
        {
            var page = CreateTabPage("BOM");
            var panel = CreateTabPanel();
            page.Controls.Add(panel);

            var paths = CreateFormLayout();
            _bomFolderText = new TextBox { Width = 200 };
            AddField(paths, "BOM folder", CreateFolderPicker(_bomFolderText, OnBrowseBomFolder));
            AddSection(panel, CreateGroupBox("BOM output", paths));

            var actions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
                Dock = DockStyle.Fill
            };
            var btnBom = new Button { Text = "Process BOM", AutoSize = true };
            btnBom.Click += OnProcessBom;
            var btnFreeze = new Button { Text = "Freeze model", AutoSize = true };
            btnFreeze.Click += (_, __) => OnFreeze(true);
            var btnUnfreeze = new Button { Text = "Unfreeze model", AutoSize = true };
            btnUnfreeze.Click += (_, __) => OnFreeze(false);

            actions.Controls.Add(btnBom);
            actions.Controls.Add(btnFreeze);
            actions.Controls.Add(btnUnfreeze);
            AddSection(panel, CreateGroupBox("Actions", actions));

            return page;
        }

        private TabPage BuildConfigTab()
        {
            var page = CreateTabPage("Configuration");
            var panel = CreateTabPanel();
            page.Controls.Add(panel);

            var templates = CreateFormLayout();
            _blankTemplateText = new TextBox { Width = 200 };
            AddField(templates, "DXF template", CreateFilePicker(_blankTemplateText, OnBrowseBlankTemplate));
            _bomTemplateText = new TextBox { Width = 200 };
            AddField(templates, "BOM template", CreateFilePicker(_bomTemplateText, OnBrowseBomTemplate));
            AddSection(panel, CreateGroupBox("Templates", templates));

            var web = CreateFormLayout();
            _weblinkText = new TextBox { Width = 200 };
            var openWeb = new Button { Text = "Open", AutoSize = true };
            openWeb.Click += OnOpenWeb;
            AddField(web, "Web", CreateInlineField(_weblinkText, openWeb));
            AddSection(panel, CreateGroupBox("Server", web));

            _removeModifiedNotesCheck = new CheckBox { Text = "Remove modified notes" };
            AddSection(panel, CreateGroupBox("Options", _removeModifiedNotesCheck));

            var configActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            var btnSave = new Button { Text = "Save configuration", AutoSize = true };
            btnSave.Click += OnSaveConfig;
            _configPathLabel = new Label { AutoSize = true };
            configActions.Controls.Add(btnSave);
            configActions.Controls.Add(_configPathLabel);
            AddSection(panel, CreateGroupBox("Config", configActions));

            return page;
        }

        private void ApplyConfig(TinyMrpConfig config)
        {
            if (config == null)
            {
                return;
            }

            if (_deliverablesFolderText != null)
            {
                _deliverablesFolderText.Text = config.DeliverablesFolder;
            }

            if (_bomFolderText != null)
            {
                _bomFolderText.Text = config.BomFolder;
            }

            if (_weblinkText != null)
            {
                _weblinkText.Text = config.WebLink;
            }

            if (_bomTemplateText != null)
            {
                _bomTemplateText.Text = config.BomTemplatePath;
            }

            if (_blankTemplateText != null)
            {
                _blankTemplateText.Text = config.BlankTemplatePath;
            }

            if (_removeModifiedNotesCheck != null)
            {
                _removeModifiedNotesCheck.Checked = config.RemoveModifiedNotes;
            }

            if (_configPathLabel != null)
            {
            _configPathLabel.Text = "Config: " + config.ConfigPath;
            }
        }

        private PublishOptions BuildOptions()
        {
            UpdateConfigFromUi();

            var options = new PublishOptions
            {
                DeliverablesFolder = _deliverablesFolderText != null ? _deliverablesFolderText.Text : string.Empty,
                BomFolder = _bomFolderText != null ? _bomFolderText.Text : string.Empty,
                ExportPngModel = _pngModelCheck != null && _pngModelCheck.Checked,
                ExportStep = _stepCheck != null && _stepCheck.Checked,
                ExportEdrawing = _edrCheck != null && _edrCheck.Checked,
                Export3mf = _threeMfCheck != null && _threeMfCheck.Checked,
                ExportPngDrawing = _pngDrawingCheck != null && _pngDrawingCheck.Checked,
                ExportPdf = _pdfCheck != null && _pdfCheck.Checked,
                ExportEdrawingDrawing = _edrDrawingCheck != null && _edrDrawingCheck.Checked,
                OverwriteFiles = _overwriteCheck != null && _overwriteCheck.Checked,
                TopLevelOnly = _topLevelOnlyCheck != null && _topLevelOnlyCheck.Checked
            };

            return options;
        }

        private void UpdateConfigFromUi()
        {
            TinyMrpConfig config = AddinContext.Config;
            if (config == null)
            {
                return;
            }

            if (_deliverablesFolderText != null)
            {
                config.DeliverablesFolder = _deliverablesFolderText.Text;
            }

            if (_bomFolderText != null)
            {
                config.BomFolder = _bomFolderText.Text;
            }

            if (_weblinkText != null)
            {
                config.WebLink = _weblinkText.Text;
            }

            if (_bomTemplateText != null)
            {
                config.BomTemplatePath = _bomTemplateText.Text;
            }

            if (_blankTemplateText != null)
            {
                config.BlankTemplatePath = _blankTemplateText.Text;
            }

            if (_removeModifiedNotesCheck != null)
            {
                config.RemoveModifiedNotes = _removeModifiedNotesCheck.Checked;
            }

            config.ResolvePaths();
        }

        private void OnCreateFiles(object sender, EventArgs e)
        {
            TinyMrpPublisher publisher = AddinContext.Publisher;
            if (publisher == null)
            {
                MessageBox.Show("Publisher is not initialized.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            PublishOptions options = BuildOptions();
            publisher.ProcessFiles(options, Log);
        }

        private void OnProcessBom(object sender, EventArgs e)
        {
            TinyMrpPublisher publisher = AddinContext.Publisher;
            if (publisher == null)
            {
                MessageBox.Show("Publisher is not initialized.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            PublishOptions options = BuildOptions();
            publisher.ProcessBom(options, Log);
        }

        private void OnFreeze(bool freeze)
        {
            TinyMrpPublisher publisher = AddinContext.Publisher;
            if (publisher == null)
            {
                MessageBox.Show("Publisher is not initialized.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            publisher.FreezeDesign(freeze, Log);
        }

        private void OnSaveConfig(object sender, EventArgs e)
        {
            TinyMrpConfig config = AddinContext.Config;
            if (config == null)
            {
                MessageBox.Show("Config is not initialized.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            try
            {
                UpdateConfigFromUi();
                config.Save();
                if (_configPathLabel != null)
                {
                    _configPathLabel.Text = "Config: " + config.ConfigPath;
                }
                MessageBox.Show("Config saved.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to save config: " + ex.Message, "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void OnOpenWeb(object sender, EventArgs e)
        {
            string url = _weblinkText != null ? _weblinkText.Text : string.Empty;
            if (string.IsNullOrWhiteSpace(url))
            {
                return;
            }

            try
            {
                string launchUrl = url.Trim();
                if (!launchUrl.Contains("://"))
                {
                    launchUrl = "http://" + launchUrl;
                }

                Process.Start(new ProcessStartInfo
                {
                    FileName = launchUrl,
                    UseShellExecute = true
                });
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to open web link: " + ex.Message, "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void OnBrowseDeliverables(object sender, EventArgs e)
        {
            string folder = BrowseFolder(_deliverablesFolderText != null ? _deliverablesFolderText.Text : string.Empty);
            if (!string.IsNullOrWhiteSpace(folder) && _deliverablesFolderText != null)
            {
                _deliverablesFolderText.Text = folder;
            }
        }

        private void OnBrowseBomFolder(object sender, EventArgs e)
        {
            string folder = BrowseFolder(_bomFolderText != null ? _bomFolderText.Text : string.Empty);
            if (!string.IsNullOrWhiteSpace(folder) && _bomFolderText != null)
            {
                _bomFolderText.Text = folder;
            }
        }

        private void OnBrowseBlankTemplate(object sender, EventArgs e)
        {
            string path = BrowseFile("Select blank template", "SolidWorks template (*.slddrt)|*.slddrt");
            if (!string.IsNullOrWhiteSpace(path) && _blankTemplateText != null)
            {
                _blankTemplateText.Text = path;
            }
        }

        private void OnBrowseBomTemplate(object sender, EventArgs e)
        {
            string path = BrowseFile("Select BOM template", "BOM template (*.sldbomtbt)|*.sldbomtbt");
            if (!string.IsNullOrWhiteSpace(path) && _bomTemplateText != null)
            {
                _bomTemplateText.Text = path;
            }
        }

        private string BrowseFolder(string initialPath)
        {
            using (var dialog = new FolderBrowserDialog())
            {
                if (!string.IsNullOrWhiteSpace(initialPath))
                {
                    dialog.SelectedPath = initialPath;
                }

                DialogResult result = dialog.ShowDialog();
                return result == DialogResult.OK ? dialog.SelectedPath : string.Empty;
            }
        }

        private string BrowseFile(string title, string filter)
        {
            using (var dialog = new OpenFileDialog())
            {
                dialog.Title = title;
                dialog.Filter = filter;
                dialog.CheckFileExists = true;

                DialogResult result = dialog.ShowDialog();
                return result == DialogResult.OK ? dialog.FileName : string.Empty;
            }
        }

        private void SetDeliverableChecks(bool value)
        {
            if (_pngModelCheck != null) _pngModelCheck.Checked = value;
            if (_stepCheck != null) _stepCheck.Checked = value;
            if (_edrCheck != null) _edrCheck.Checked = value;
            if (_threeMfCheck != null) _threeMfCheck.Checked = value;
            if (_pngDrawingCheck != null) _pngDrawingCheck.Checked = value;
            if (_pdfCheck != null) _pdfCheck.Checked = value;
            if (_edrDrawingCheck != null) _edrDrawingCheck.Checked = value;
        }

        private void Log(string message)
        {
            if (_logBox == null)
            {
                return;
            }

            if (_logBox.InvokeRequired)
            {
                _logBox.BeginInvoke(new Action<string>(Log), message);
                return;
            }

            _logBox.AppendText(message + Environment.NewLine);
        }

        private static TabPage CreateTabPage(string title)
        {
            return new TabPage(title)
            {
                BackColor = SystemColors.Control,
                Padding = new Padding(4)
            };
        }

        private static TableLayoutPanel CreateTabPanel()
        {
            var panel = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true,
                Padding = new Padding(6),
                ColumnCount = 1,
                RowCount = 0,
                GrowStyle = TableLayoutPanelGrowStyle.AddRows
            };
            panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));
            return panel;
        }

        private static void AddSection(TableLayoutPanel panel, Control control)
        {
            if (panel == null || control == null)
            {
                return;
            }

            control.Dock = DockStyle.Top;
            control.Margin = new Padding(0, 0, 0, 8);

            int row = panel.RowCount;
            panel.RowCount++;
            panel.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            panel.Controls.Add(control, 0, row);
        }

        private static GroupBox CreateGroupBox(string title, Control content)
        {
            var box = new GroupBox
            {
                Text = title,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Padding = new Padding(8)
            };

            if (content.Dock == DockStyle.None)
            {
                content.Dock = DockStyle.Top;
            }
            box.Controls.Add(content);
            return box;
        }

        private static TableLayoutPanel CreateFormLayout()
        {
            var table = new TableLayoutPanel
            {
                ColumnCount = 2,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink
            };
            table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 40F));
            table.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 60F));
            return table;
        }

        private static void AddField(TableLayoutPanel table, string labelText, Control control)
        {
            int row = table.RowCount;
            table.RowCount++;
            table.RowStyles.Add(new RowStyle(SizeType.AutoSize));

            var label = new Label { Text = labelText, AutoSize = true, Anchor = AnchorStyles.Left };
            control.Anchor = AnchorStyles.Left | AnchorStyles.Right;
            table.Controls.Add(label, 0, row);
            table.Controls.Add(control, 1, row);
        }

        private static Control CreateFolderPicker(TextBox target, EventHandler onBrowse)
        {
            return CreateInlineField(target, CreateBrowseButton(onBrowse));
        }

        private static Control CreateFilePicker(TextBox target, EventHandler onBrowse)
        {
            return CreateInlineField(target, CreateBrowseButton(onBrowse));
        }

        private static Control CreateInlineField(TextBox textBox, Control trailingControl)
        {
            var panel = new Panel { Dock = DockStyle.Fill, Height = 26 };
            textBox.Dock = DockStyle.Fill;
            trailingControl.Dock = DockStyle.Right;
            panel.Controls.Add(textBox);
            panel.Controls.Add(trailingControl);
            return panel;
        }

        private static Button CreateBrowseButton(EventHandler onBrowse)
        {
            var btn = new Button { Text = "...", Width = 28, Height = 24 };
            btn.Click += onBrowse;
            return btn;
        }
    }
}
