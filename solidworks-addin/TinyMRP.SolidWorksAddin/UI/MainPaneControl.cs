using System;
using System.Diagnostics;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;
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
        private TextBox _weblinkText;
        private TextBox _bomTemplateText;
        private TextBox _blankTemplateText;
        private TextBox _dxfSheetNamesText;
        private CheckBox _removeModifiedNotesCheck;
        private CheckBox _topLevelOnlyCheck;
        private CheckBox _overwriteCheck;
        private CheckBox _uploadPackIncludeDeliverablesCheck;
        private CheckBox _uploadPackIncludeExtrasCheck;
        private Button _assocFilesButton;
        private CheckBox _pngModelCheck;
        private CheckBox _stepCheck;
        private CheckBox _edrCheck;
        private CheckBox _threeMfCheck;
        private CheckBox _plyCheck;
        private CheckBox _stlCheck;
        private CheckBox _pngDrawingCheck;
        private CheckBox _pdfCheck;
        private CheckBox _dxfCheck;
        private CheckBox _edrDrawingCheck;
        private ProgressBar _publishProgressBar;
        private Label _publishProgressLabel;
        private ProgressBar _bomProgressBar;
        private Label _bomProgressLabel;
        private Label _actionStatusLabel;
        private Button _cancelButton;
        private LinkLabel _openLogLink;
        private string _lastRunLogPath = string.Empty;
        private ProgressBar _toolsProgressBar;
        private Label _toolsProgressLabel;
        private Label _toolsStatusLabel;
        private Button _toolsCancelButton;
        private string _toolsActionName = "Tools";
        private Label _configPathLabel;
        private CheckBox _hideAllConfigsCheck;
        private CheckBox _hideOriginCheck;
        private CheckBox _hidePlaneCheck;
        private CheckBox _hideAxisCheck;
        private CheckBox _hidePointCheck;
        private CheckBox _hideCoordSysCheck;
        private CheckBox _hideSketch2DCheck;
        private CheckBox _hideSketch3DCheck;
        private CheckBox _hideSpline3DCheck;
        private CheckBox _hideCompositeCurveCheck;
        private CheckBox _hideHelixCheck;
        private CheckBox _hideEnvelopeCheck;
        private TextBox _backendUrlText;
        private TextBox _authTokenText;
        private TextBox _quickBackendUrlText;
        private TextBox _quickAuthTokenText;
        private ComboBox _quickSchemeCombo;
        private Button _quickRefreshSchemesButton;
        private ComboBox _quickApplyModeCombo;
        private TextBox _quickPartNumberPropText;
        private TextBox _quickRevisionPropText;
        private TextBox _quickDisplayCodePropText;
        private Label _quickPreviewLabel;
        private Button _quickDiagnosticsButton;
        private Button _numberingPreviewButton;
        private Button _numberingAllocateButton;
        private Button _numberingAllocateSaveButton;
        private Button _numberingAllocateRenameButton;
        private ComboBox _numberingPresetCombo;
        private Button _numberingPresetRefreshButton;
        private TextBox _numberingPreviewPartText;
        private TextBox _numberingPreviewRevisionText;
        private TextBox _numberingPreviewDisplayText;
        private Label _numberingStatusLabel;
        private FlowLayoutPanel _numberingSeqOverridePanel;
        private GroupBox _numberingSeqOverrideGroup;
        private Label _numberingSeqOverrideNote;
        private readonly List<NumericUpDown> _numberingSeqOverrides = new List<NumericUpDown>();
        private readonly Dictionary<string, List<int>> _sequenceOverrideCache = new Dictionary<string, List<int>>(StringComparer.OrdinalIgnoreCase);
        private CheckBox _renameAutoCheck;
        private ComboBox _renameModeCombo;
        private CheckBox _renameAppendRevisionCheck;
        private CheckBox _renameKeepBackupCheck;
        private CheckBox _renameChildrenCheck;
        private Button _renameDryRunButton;
        private CheckBox _autoAssignGenericCheck;
        private CheckBox _autoAssignAnyNameCheck;
        private TextBox _numberingPartNumberPropText;
        private TextBox _numberingRevisionPropText;
        private TextBox _numberingDisplayCodePropText;
        private ComboBox _advancedSchemeCombo;
        private ComboBox _advancedApplyModeCombo;
        private TextBox _advancedContextJsonText;
        private TextBox _partNumberPropText;
        private TextBox _revisionPropText;
        private TextBox _displayCodePropText;
        private bool _syncingConfigFields;
        private readonly Dictionary<string, Control[]> _quickContextRows = new Dictionary<string, Control[]>(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, Control[]> _numberingContextRows = new Dictionary<string, Control[]>(StringComparer.OrdinalIgnoreCase);
        private ComboBox _schemeCombo;
        private Button _schemeRefreshButton;
        private TextBox _schemeNameText;
        private TextBox _schemeDescriptionText;
        private CheckBox _schemeActiveCheck;
        private CheckBox _schemePresetCheck;
        private CheckBox _schemeRecommendedCheck;
        private ComboBox _schemeVisibilityCombo;
        private ComboBox _presetCombo;
        private TextBox _separatorText;
        private ComboBox _scopeModeCombo;
        private TextBox _scopeKeysText;
        private NumericUpDown _seqPaddingUpDown;
        private ComboBox _seqBaseCombo;
        private NumericUpDown _seqStartUpDown;
        private ComboBox _seqResetCombo;
        private ComboBox _revPolicyCombo;
        private TextBox _revStartText;
        private NumericUpDown _maxLengthUpDown;
        private TextBox _allowedCharsetText;
        private CheckBox _requireSeqCheck;
        private ListBox _segmentsList;
        private ComboBox _segmentKindCombo;
        private TextBox _segmentLiteralText;
        private NumericUpDown _segmentSeqPaddingUpDown;
        private ComboBox _segmentSeqBaseCombo;
        private NumericUpDown _segmentSeqStartUpDown;
        private CheckBox _segmentSeqAutoCheck;
        private ComboBox _segmentDateFmtCombo;
        private Label _validationResultLabel;
        private Label _previewResultLabel;
        private ComboBox _revisionActionCombo;
        private TextBox _existingPartNumberText;
        private CheckBox _createPartCheck;
        private ComboBox _applyScopeCombo;
        private CheckBox _applyDocPropsCheck;
        private CheckedListBox _configListBox;
        private Button _loadConfigsButton;
        private Label _allocateResultLabel;
        private NumberingApiClient _numberingClient;
        private NumberingSchemeDefinition _currentScheme;
        private readonly List<NumberingSchemeDefinition> _loadedSchemes = new List<NumberingSchemeDefinition>();
        private readonly HashSet<string> _autoAssignedModels = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

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
            _tabs.TabPages.Add(BuildPublishBomTab());
            _tabs.TabPages.Add(BuildToolsTab());
            _tabs.TabPages.Add(BuildNumberingTab());
            _tabs.TabPages.Add(BuildConfigTab());
            InitializeNumberingDefaults();
        }

        private TabPage BuildPublishBomTab()
        {
            var page = CreateTabPage("Publish/BOM");
            var panel = CreateTabPanel();
            page.Controls.Add(panel);

            var modelChecks = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            _pngModelCheck = CreateCheckBox("PNG");
            _stepCheck = CreateCheckBox("STEP");
            _edrCheck = CreateCheckBox("eDrawings");
            _threeMfCheck = CreateCheckBox("3MF");
            _plyCheck = CreateCheckBox("PLY");
            _stlCheck = CreateCheckBox("STL");
            modelChecks.Controls.Add(_pngModelCheck);
            modelChecks.Controls.Add(_stepCheck);
            modelChecks.Controls.Add(_edrCheck);
            modelChecks.Controls.Add(_threeMfCheck);
            modelChecks.Controls.Add(_plyCheck);
            modelChecks.Controls.Add(_stlCheck);

            var drawingChecks = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            _pngDrawingCheck = CreateCheckBox("PNG drawing");
            _pdfCheck = CreateCheckBox("PDF");
            _dxfCheck = CreateCheckBox("DXF");
            _edrDrawingCheck = CreateCheckBox("eDrawings drawing");
            drawingChecks.Controls.Add(_pngDrawingCheck);
            drawingChecks.Controls.Add(_pdfCheck);
            drawingChecks.Controls.Add(_dxfCheck);
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
            modelsBox.AutoSize = true;
            modelsBox.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            modelsBox.Dock = DockStyle.Top;
            modelsBox.MinimumSize = new Size(160, 0);

            var drawingsBox = CreateGroupBox("Drawings", drawingChecks);
            drawingsBox.AutoSize = true;
            drawingsBox.AutoSizeMode = AutoSizeMode.GrowAndShrink;
            drawingsBox.Dock = DockStyle.Top;
            drawingsBox.MinimumSize = new Size(160, 0);

            deliverablesLayout.Controls.Add(modelsBox, 0, 0);
            deliverablesLayout.Controls.Add(drawingsBox, 1, 0);
            AddSection(panel, CreateGroupBox("Deliverables", deliverablesLayout));

            var optionsPanel = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
                Dock = DockStyle.Fill
            };
            _overwriteCheck = CreateCheckBox("Overwrite files");
            _topLevelOnlyCheck = CreateCheckBox("Top level only");
            optionsPanel.Controls.Add(_overwriteCheck);
            optionsPanel.Controls.Add(_topLevelOnlyCheck);
            AddSection(panel, CreateGroupBox("Options", optionsPanel));

            var assocPanel = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
                Dock = DockStyle.Fill
            };
            _assocFilesButton = new Button { Text = "Manage associated files...", AutoSize = true };
            _assocFilesButton.Click += OnManageAssociatedFiles;
            assocPanel.Controls.Add(_assocFilesButton);
            AddSection(panel, CreateGroupBox("Associated files", assocPanel));

            var uploadPackOptions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            _uploadPackIncludeDeliverablesCheck = CreateCheckBox("Include deliverables (uses selections above)");
            _uploadPackIncludeExtrasCheck = CreateCheckBox("Include associated files");
            if (_uploadPackIncludeDeliverablesCheck != null) _uploadPackIncludeDeliverablesCheck.Checked = true;
            if (_uploadPackIncludeExtrasCheck != null) _uploadPackIncludeExtrasCheck.Checked = true;
            uploadPackOptions.Controls.Add(_uploadPackIncludeDeliverablesCheck);
            uploadPackOptions.Controls.Add(_uploadPackIncludeExtrasCheck);
            AddSection(panel, CreateGroupBox("Upload pack options", uploadPackOptions));

            var publishActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            var btnSelectAll = new Button { Text = "Select all", AutoSize = true };
            btnSelectAll.Click += (_, __) => SetDeliverableChecks(true);
            var btnDeselectAll = new Button { Text = "Deselect", AutoSize = true };
            btnDeselectAll.Click += (_, __) => SetDeliverableChecks(false);
            var btnCreate = new Button { Text = "Create files", AutoSize = true };
            btnCreate.Click += OnCreateFiles;
            var btnResume = new Button { Text = "Resume last export", AutoSize = true };
            btnResume.Click += OnResumeLastExport;
            publishActions.Controls.Add(btnSelectAll);
            publishActions.Controls.Add(btnDeselectAll);
            publishActions.Controls.Add(btnCreate);
            publishActions.Controls.Add(btnResume);
            AddSection(panel, CreateGroupBox("Publish actions", publishActions));

            var uploadPackActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            var btnUploadPack = new Button { Text = "Create upload pack", AutoSize = true };
            btnUploadPack.Click += OnCreateUploadPack;
            uploadPackActions.Controls.Add(btnUploadPack);
            uploadPackActions.Controls.Add(new Label
            {
                Text = "Only the deliverables selected above will be included.",
                AutoSize = true,
                ForeColor = SystemColors.GrayText,
                MaximumSize = new Size(260, 0),
                Padding = new Padding(0, 2, 0, 0)
            });
            AddSection(panel, CreateGroupBox("Upload pack actions", uploadPackActions));

            var bomActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            var btnBom = new Button { Text = "Process BOM", AutoSize = true };
            btnBom.Click += OnProcessBom;

            bomActions.Controls.Add(btnBom);
            AddSection(panel, CreateGroupBox("BOM actions", bomActions));

            var progressLayout = new TableLayoutPanel
            {
                ColumnCount = 2,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Dock = DockStyle.Fill
            };
            progressLayout.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            progressLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));

            _publishProgressBar = new ProgressBar { Minimum = 0, Maximum = 100, Dock = DockStyle.Fill, Height = 18 };
            _publishProgressLabel = new Label { AutoSize = true, Text = "Create files: idle" };
            AddProgressRow(progressLayout, "Create files", _publishProgressBar, _publishProgressLabel);

            _bomProgressBar = new ProgressBar { Minimum = 0, Maximum = 100, Dock = DockStyle.Fill, Height = 18 };
            _bomProgressLabel = new Label { AutoSize = true, Text = "Process BOM: idle" };
            AddProgressRow(progressLayout, "Process BOM", _bomProgressBar, _bomProgressLabel);

            _actionStatusLabel = new Label { AutoSize = true, Text = "" };
            _cancelButton = new Button { Text = "Stop process", AutoSize = true };
            _cancelButton.Click += OnStopProcess;
            _openLogLink = new LinkLabel { AutoSize = true, Text = "Open last run log", Visible = false };
            _openLogLink.LinkClicked += (_, __) => TryOpenLastRunLog();
            var progressWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            progressWrap.Controls.Add(progressLayout);
            progressWrap.Controls.Add(_actionStatusLabel);
            progressWrap.Controls.Add(_cancelButton);
            progressWrap.Controls.Add(_openLogLink);
            AddSection(panel, CreateGroupBox("Progress", progressWrap));

            return page;
        }

        private TabPage BuildToolsTab()
        {
            var page = CreateTabPage("Tools");
            var panel = CreateTabPanel();
            page.Controls.Add(panel);

            var modelActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };

            var btnFreeze = new Button { Text = "Freeze model", AutoSize = true };
            btnFreeze.Click += (_, __) => OnFreeze(true);
            var btnUnfreeze = new Button { Text = "Unfreeze model", AutoSize = true };
            btnUnfreeze.Click += (_, __) => OnFreeze(false);
            var btnNormalize = new Button { Text = "Normalize units", AutoSize = true };
            btnNormalize.Click += OnNormalizeUnits;

            modelActions.Controls.Add(btnFreeze);
            modelActions.Controls.Add(btnUnfreeze);
            modelActions.Controls.Add(btnNormalize);
            AddSection(panel, CreateGroupBox("Model utilities", modelActions));

            var hideOptionsLayout = new TableLayoutPanel
            {
                ColumnCount = 2,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Dock = DockStyle.Fill,
                Padding = new Padding(0, 4, 0, 2)
            };
            hideOptionsLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50F));
            hideOptionsLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50F));

            var hideRefPanel = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            _hideOriginCheck = CreateCheckBox("Origin");
            _hidePlaneCheck = CreateCheckBox("Reference planes");
            _hideAxisCheck = CreateCheckBox("Reference axes");
            _hidePointCheck = CreateCheckBox("Reference points");
            _hideCoordSysCheck = CreateCheckBox("Coordinate systems");
            hideRefPanel.Controls.Add(_hideOriginCheck);
            hideRefPanel.Controls.Add(_hidePlaneCheck);
            hideRefPanel.Controls.Add(_hideAxisCheck);
            hideRefPanel.Controls.Add(_hidePointCheck);
            hideRefPanel.Controls.Add(_hideCoordSysCheck);

            var hideSketchPanel = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            _hideSketch2DCheck = CreateCheckBox("2D sketches");
            _hideSketch3DCheck = CreateCheckBox("3D sketches");
            _hideSpline3DCheck = CreateCheckBox("3D spline curves");
            _hideCompositeCurveCheck = CreateCheckBox("Composite curves");
            _hideHelixCheck = CreateCheckBox("Helix");
            hideSketchPanel.Controls.Add(_hideSketch2DCheck);
            hideSketchPanel.Controls.Add(_hideSketch3DCheck);
            hideSketchPanel.Controls.Add(_hideSpline3DCheck);
            hideSketchPanel.Controls.Add(_hideCompositeCurveCheck);
            hideSketchPanel.Controls.Add(_hideHelixCheck);

            hideOptionsLayout.Controls.Add(hideRefPanel, 0, 0);
            hideOptionsLayout.Controls.Add(hideSketchPanel, 1, 0);

            var hideActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill,
                Padding = new Padding(0, 2, 0, 0)
            };
            _hideAllConfigsCheck = CreateCheckBox("All configurations");
            _hideEnvelopeCheck = CreateCheckBox("Hide envelope components");
            var btnHideSelectAll = new Button { Text = "Select all", AutoSize = true };
            btnHideSelectAll.Click += (_, __) => SetHideFeatureChecks(true);
            var btnHideSelectNone = new Button { Text = "Clear", AutoSize = true };
            btnHideSelectNone.Click += (_, __) => SetHideFeatureChecks(false);
            hideActions.Controls.Add(_hideAllConfigsCheck);
            hideActions.Controls.Add(_hideEnvelopeCheck);
            hideActions.Controls.Add(btnHideSelectAll);
            hideActions.Controls.Add(btnHideSelectNone);

            var hideApplyWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
                Dock = DockStyle.Fill,
                Padding = new Padding(0, 2, 0, 0)
            };
            var btnHideApply = new Button { Text = "Hide selected features", AutoSize = true };
            btnHideApply.Click += OnHideFeatures;
            hideApplyWrap.Controls.Add(btnHideApply);

            var hideWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            hideWrap.Controls.Add(hideOptionsLayout);
            hideWrap.Controls.Add(hideActions);
            hideWrap.Controls.Add(hideApplyWrap);
            AddSection(panel, CreateGroupBox("Hide sketches and reference geometry", hideWrap));

            var toolsProgressLayout = new TableLayoutPanel
            {
                ColumnCount = 2,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Dock = DockStyle.Fill
            };
            toolsProgressLayout.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            toolsProgressLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));

            _toolsProgressBar = new ProgressBar { Minimum = 0, Maximum = 100, Dock = DockStyle.Fill, Height = 18 };
            _toolsProgressLabel = new Label { AutoSize = true, Text = "Tools: idle" };
            AddProgressRow(toolsProgressLayout, "Tools", _toolsProgressBar, _toolsProgressLabel);

            _toolsStatusLabel = new Label { AutoSize = true, Text = "" };
            _toolsCancelButton = new Button { Text = "Cancel current task", AutoSize = true };
            _toolsCancelButton.Click += OnCancelCurrentTask;
            var toolsWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            toolsWrap.Controls.Add(toolsProgressLayout);
            toolsWrap.Controls.Add(_toolsStatusLabel);
            toolsWrap.Controls.Add(_toolsCancelButton);
            AddSection(panel, CreateGroupBox("Progress", toolsWrap));

            return page;
        }

        private TabPage BuildNumberingTab()
        {
            var page = CreateTabPage("Numbering");
            var panel = CreateTabPanel();
            page.Controls.Add(panel);

            var commandStrip = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
                Dock = DockStyle.Fill
            };
            _numberingPreviewButton = CreateCommandButton("Preview Partnumber", OnNumberingPreview);
            _numberingAllocateButton = CreateCommandButton("Allocate & Apply", OnNumberingAllocate);
            _numberingAllocateButton.Visible = false;
            _numberingAllocateSaveButton = CreateCommandButton("Allocate and Save", OnNumberingAllocateSave);
            _numberingAllocateRenameButton = CreateCommandButton("Allocate and rename", OnNumberingAllocateRename);
            commandStrip.Controls.Add(_numberingPreviewButton);
            commandStrip.Controls.Add(_numberingAllocateButton);
            commandStrip.Controls.Add(_numberingAllocateSaveButton);
            commandStrip.Controls.Add(_numberingAllocateRenameButton);
            AddSection(panel, commandStrip);

            var quickLayout = CreateFormLayout();
            quickLayout.Dock = DockStyle.Fill;
            _numberingPresetCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 220 };
            _numberingPresetCombo.SelectedIndexChanged += OnNumberingPresetSelected;
            _numberingPresetRefreshButton = new Button { Text = "Refresh", AutoSize = true };
            _numberingPresetRefreshButton.Click += OnRefreshSchemes;
            AddField(quickLayout, "Numbering scheme", CreateInlineField(_numberingPresetCombo, _numberingPresetRefreshButton));

            var previewBox = new TableLayoutPanel
            {
                ColumnCount = 2,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Dock = DockStyle.Fill,
                MinimumSize = new Size(260, 0)
            };
            previewBox.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 40F));
            previewBox.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 60F));
            _numberingPreviewPartText = CreateReadOnlyPreview();
            AddField(previewBox, "Part number", _numberingPreviewPartText);
            _numberingPreviewRevisionText = CreateReadOnlyPreview();
            AddField(previewBox, "Revision", _numberingPreviewRevisionText);
            _numberingPreviewDisplayText = CreateReadOnlyPreview();
            AddField(previewBox, "Display code", _numberingPreviewDisplayText);
            _numberingPreviewRevisionText.Visible = false;
            _numberingPreviewDisplayText.Visible = false;
            SetFieldLabelVisible(previewBox, "Revision", false);
            SetFieldLabelVisible(previewBox, "Display code", false);

            _numberingStatusLabel = new Label
            {
                AutoSize = true,
                Text = "Ready.",
                ForeColor = SystemColors.GrayText,
                Padding = new Padding(0, 4, 0, 0)
            };

            var quickWrap = CreateStackPanel();
            AddStackRow(quickWrap, quickLayout);
            _numberingSeqOverridePanel = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            _numberingSeqOverrideNote = new Label
            {
                Text = "Save the scheme in Advanced to persist overrides.",
                AutoSize = true,
                ForeColor = SystemColors.GrayText,
                MaximumSize = new Size(240, 0),
                Padding = new Padding(0, 2, 0, 0)
            };
            _numberingSeqOverrideGroup = CreateGroupBox("Sequence start override", _numberingSeqOverridePanel);
            _numberingSeqOverrideGroup.Visible = false;
            AddStackRow(quickWrap, _numberingSeqOverrideGroup);
            AddStackRow(quickWrap, CreateGroupBox("Preview", previewBox));
            AddStackRow(quickWrap, _numberingStatusLabel);
            AddSection(panel, CreateGroupBox("Quick setup", quickWrap));
            return page;
        }

        private Control BuildNumberingAdvancedPanel()
        {
            var panel = CreateStackPanel();

            var schemeLayout = CreateFormLayout();
            _schemeCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 200 };
            _schemeCombo.SelectedIndexChanged += OnSchemeSelected;
            _schemeRefreshButton = new Button { Text = "Refresh", AutoSize = true };
            _schemeRefreshButton.Click += OnRefreshSchemes;
            AddField(schemeLayout, "Scheme", CreateInlineField(_schemeCombo, _schemeRefreshButton));

            _schemeNameText = new TextBox { Width = 200 };
            AddField(schemeLayout, "Name", _schemeNameText);
            _schemeDescriptionText = new TextBox { Width = 200 };
            AddField(schemeLayout, "Description", _schemeDescriptionText);
            _schemeActiveCheck = new CheckBox { Text = "Active", AutoSize = true };
            AddField(schemeLayout, "Status", _schemeActiveCheck);
            _schemePresetCheck = new CheckBox { Text = "Preset", AutoSize = true };
            AddField(schemeLayout, "Preset", _schemePresetCheck);
            _schemeRecommendedCheck = new CheckBox { Text = "Recommended", AutoSize = true };
            AddField(schemeLayout, "Recommended", _schemeRecommendedCheck);
            _schemeVisibilityCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 160 };
            _schemeVisibilityCombo.Items.AddRange(new object[] { "quickstart", "advanced_only" });
            AddField(schemeLayout, "Visibility", _schemeVisibilityCombo);
            AddSection(panel, CreateGroupBox("Scheme", schemeLayout));

            var mapLayout = CreateFormLayout();
            _numberingPartNumberPropText = new TextBox { Width = 200 };
            AddField(mapLayout, "Part number property", _numberingPartNumberPropText);
            _numberingRevisionPropText = new TextBox { Width = 200 };
            AddField(mapLayout, "Revision property", _numberingRevisionPropText);
            _numberingDisplayCodePropText = new TextBox { Width = 200 };
            AddField(mapLayout, "Display code property", _numberingDisplayCodePropText);
            AddSection(panel, CreateGroupBox("Property mapping", mapLayout));

            var previewActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            var btnPreview = new Button { Text = "Preview (advanced)", AutoSize = true };
            btnPreview.Click += OnPreviewNext;
            _previewResultLabel = new Label { AutoSize = true, Text = "" };
            var btnSaveDefaults = new Button { Text = "Save defaults", AutoSize = true };
            btnSaveDefaults.Click += OnSaveNumberingDefaults;
            previewActions.Controls.Add(btnPreview);
            previewActions.Controls.Add(btnSaveDefaults);
            previewActions.Controls.Add(_previewResultLabel);
            AddSection(panel, CreateGroupBox("Advanced preview", previewActions));

            var allocateLayout = CreateFormLayout();
            _revisionActionCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 180 };
            _revisionActionCombo.Items.AddRange(new object[] { "new_part", "revise_existing", "keep_existing" });
            AddField(allocateLayout, "Revision action", _revisionActionCombo);
            _existingPartNumberText = new TextBox { Width = 160 };
            AddField(allocateLayout, "Existing PN", _existingPartNumberText);
            _applyScopeCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 200 };
            _applyScopeCombo.Items.AddRange(new object[] { "Active configuration", "All configurations", "Selected configurations" });
            AddField(allocateLayout, "Apply to", _applyScopeCombo);
            _applyDocPropsCheck = new CheckBox { Text = "Also document properties", AutoSize = true };
            AddField(allocateLayout, "Document props", _applyDocPropsCheck);
            _createPartCheck = new CheckBox { Text = "Create/update part on server", AutoSize = true };
            AddField(allocateLayout, "Server record", _createPartCheck);

            var allocateActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            var btnAllocate = new Button { Text = "Allocate (advanced)", AutoSize = true };
            btnAllocate.Click += OnAllocateNumber;
            _allocateResultLabel = new Label { AutoSize = true, Text = "" };
            allocateActions.Controls.Add(btnAllocate);
            allocateActions.Controls.Add(_allocateResultLabel);

            var allocateWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            allocateWrap.Controls.Add(allocateLayout);
            allocateWrap.Controls.Add(allocateActions);
            AddSection(panel, CreateGroupBox("Advanced allocation", allocateWrap));

            var renameAdvancedWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            _renameChildrenCheck = CreateCheckBox("Rename children in assemblies");
            _autoAssignAnyNameCheck = CreateCheckBox("Allow auto-assign for any name (dangerous)");
            _autoAssignAnyNameCheck.CheckedChanged += (_, __) => MaybeAutoAssignNumbering(true);
            _renameDryRunButton = new Button { Text = "Dry run rename", AutoSize = true };
            _renameDryRunButton.Click += OnRenameDryRun;
            renameAdvancedWrap.Controls.Add(_renameChildrenCheck);
            renameAdvancedWrap.Controls.Add(_autoAssignAnyNameCheck);
            renameAdvancedWrap.Controls.Add(_renameDryRunButton);
            AddSection(panel, CreateGroupBox("Rename (advanced)", renameAdvancedWrap));

            var configListWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            _configListBox = new CheckedListBox { Height = 120, Dock = DockStyle.Fill };
            var configButtons = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false
            };
            _loadConfigsButton = new Button { Text = "Load configurations", AutoSize = true };
            _loadConfigsButton.Click += OnLoadConfigurations;
            var btnConfigAll = new Button { Text = "Select all", AutoSize = true };
            btnConfigAll.Click += (_, __) => SetConfigSelection(true);
            var btnConfigClear = new Button { Text = "Clear", AutoSize = true };
            btnConfigClear.Click += (_, __) => SetConfigSelection(false);
            configButtons.Controls.Add(_loadConfigsButton);
            configButtons.Controls.Add(btnConfigAll);
            configButtons.Controls.Add(btnConfigClear);
            configListWrap.Controls.Add(_configListBox);
            configListWrap.Controls.Add(configButtons);
            AddSection(panel, CreateGroupBox("Configurations", configListWrap));

            var schemeEditor = BuildSchemeEditorPanel();
            AddSection(panel, CreateCollapsibleSection("Scheme builder", schemeEditor, false));

            return panel;
        }

        private Control BuildSchemeEditorPanel()
        {
            var panel = CreateStackPanel();

            var presetPanel = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
                Dock = DockStyle.Fill
            };
            _presetCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 220 };
            _presetCombo.Items.AddRange(new object[]
            {
                "Template: PART-SEQ6"
            });
            var btnApplyPreset = new Button { Text = "Apply template", AutoSize = true };
            btnApplyPreset.Click += OnApplyPreset;
            presetPanel.Controls.Add(_presetCombo);
            presetPanel.Controls.Add(btnApplyPreset);
            AddSection(panel, CreateGroupBox("Templates", presetPanel));

            var patternLayout = CreateFormLayout();
            _separatorText = new TextBox { Width = 80 };
            AddField(patternLayout, "Separator", _separatorText);
            _scopeModeCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 200 };
            _scopeModeCombo.Items.AddRange(new object[] { "global", "by_type", "by_project", "by_family", "custom_keys" });
            AddField(patternLayout, "Scope mode", _scopeModeCombo);
            _scopeKeysText = new TextBox { Width = 200 };
            AddField(patternLayout, "Scope keys", _scopeKeysText);
            AddSection(panel, CreateGroupBox("Pattern settings", patternLayout));

            var segmentListLayout = new TableLayoutPanel
            {
                ColumnCount = 2,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Dock = DockStyle.Fill,
                MinimumSize = new Size(240, 0)
            };
            segmentListLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));
            segmentListLayout.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));

            _segmentsList = new ListBox { Height = 140, Dock = DockStyle.Fill, MinimumSize = new Size(200, 120) };
            _segmentsList.SelectedIndexChanged += OnSegmentSelected;
            var segmentButtons = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false
            };
            var btnSegUp = new Button { Text = "Up", AutoSize = true };
            btnSegUp.Click += OnMoveSegmentUp;
            var btnSegDown = new Button { Text = "Down", AutoSize = true };
            btnSegDown.Click += OnMoveSegmentDown;
            var btnSegRemove = new Button { Text = "Remove", AutoSize = true };
            btnSegRemove.Click += OnRemoveSegment;
            segmentButtons.Controls.Add(btnSegUp);
            segmentButtons.Controls.Add(btnSegDown);
            segmentButtons.Controls.Add(btnSegRemove);
            segmentListLayout.Controls.Add(_segmentsList, 0, 0);
            segmentListLayout.Controls.Add(segmentButtons, 1, 0);
            AddSection(panel, CreateGroupBox("Segments", segmentListLayout));

            var segmentForm = CreateFormLayout();
            _segmentKindCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 200 };
            _segmentKindCombo.Items.AddRange(new object[] { "literal", "seq", "date" });
            _segmentKindCombo.SelectedIndexChanged += (_, __) => UpdateSegmentEditorState();
            AddField(segmentForm, "Kind", _segmentKindCombo);
            _segmentLiteralText = new TextBox { Width = 200 };
            AddField(segmentForm, "Literal value", _segmentLiteralText);
            _segmentSeqPaddingUpDown = new NumericUpDown { Width = 80, Minimum = 1, Maximum = 12, Value = 6 };
            AddField(segmentForm, "Seq padding", _segmentSeqPaddingUpDown);
            _segmentSeqBaseCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 80 };
            _segmentSeqBaseCombo.Items.AddRange(new object[] { "10", "36" });
            AddField(segmentForm, "Seq base", _segmentSeqBaseCombo);
            _segmentSeqStartUpDown = new NumericUpDown { Width = 80, Minimum = 1, Maximum = 999999, Value = 1 };
            AddField(segmentForm, "Manual start", _segmentSeqStartUpDown);
            _segmentSeqAutoCheck = new CheckBox { Text = "Automatic counter", AutoSize = true };
            _segmentSeqAutoCheck.CheckedChanged += (_, __) => UpdateSegmentEditorState();
            AddField(segmentForm, "Seq mode", _segmentSeqAutoCheck);
            _segmentDateFmtCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 120 };
            _segmentDateFmtCombo.Items.AddRange(new object[] { "YYYY", "YY", "MM", "YYYYMM" });
            AddField(segmentForm, "Date format", _segmentDateFmtCombo);

            var segmentActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            var btnSegAdd = new Button { Text = "Add", AutoSize = true };
            btnSegAdd.Click += OnAddSegment;
            var btnSegUpdate = new Button { Text = "Update", AutoSize = true };
            btnSegUpdate.Click += OnUpdateSegment;
            var btnSegClear = new Button { Text = "Clear", AutoSize = true };
            btnSegClear.Click += (_, __) => ClearSegmentEditor();
            segmentActions.Controls.Add(btnSegAdd);
            segmentActions.Controls.Add(btnSegUpdate);
            segmentActions.Controls.Add(btnSegClear);

            var segmentWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            segmentWrap.Controls.Add(segmentForm);
            segmentWrap.Controls.Add(segmentActions);
            AddSection(panel, CreateGroupBox("Segment editor", segmentWrap));

            var seqLayout = CreateFormLayout();
            _seqPaddingUpDown = new NumericUpDown { Width = 80, Minimum = 1, Maximum = 12, Value = 6 };
            AddField(seqLayout, "Default padding", _seqPaddingUpDown);
            _seqBaseCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 80 };
            _seqBaseCombo.Items.AddRange(new object[] { "10", "36" });
            AddField(seqLayout, "Base", _seqBaseCombo);
            _seqStartUpDown = new NumericUpDown { Width = 80, Minimum = 1, Maximum = 999999, Value = 1 };
            AddField(seqLayout, "Auto start", _seqStartUpDown);
            _seqResetCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 120 };
            _seqResetCombo.Items.AddRange(new object[] { "never", "yearly", "monthly", "by_project" });
            AddField(seqLayout, "Reset policy", _seqResetCombo);
            AddSection(panel, CreateGroupBox("Sequence defaults", seqLayout));

            var revLayout = CreateFormLayout();
            _revPolicyCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 120 };
            _revPolicyCombo.Items.AddRange(new object[] { "alpha", "numeric", "none" });
            AddField(revLayout, "Policy", _revPolicyCombo);
            _revStartText = new TextBox { Width = 80 };
            AddField(revLayout, "Start", _revStartText);
            AddSection(panel, CreateGroupBox("Revision policy", revLayout));

            var validationLayout = CreateFormLayout();
            _maxLengthUpDown = new NumericUpDown { Width = 80, Minimum = 8, Maximum = 64, Value = 32 };
            AddField(validationLayout, "Max length", _maxLengthUpDown);
            _allowedCharsetText = new TextBox { Width = 200 };
            AddField(validationLayout, "Allowed charset", _allowedCharsetText);
            _requireSeqCheck = new CheckBox { Text = "Require sequence segment", AutoSize = true };
            AddField(validationLayout, "Require seq", _requireSeqCheck);
            AddSection(panel, CreateGroupBox("Validation", validationLayout));

            var schemeActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            var btnValidate = new Button { Text = "Validate scheme", AutoSize = true };
            btnValidate.Click += OnValidateScheme;
            var btnSaveScheme = new Button { Text = "Save scheme", AutoSize = true };
            btnSaveScheme.Click += OnSaveScheme;
            var btnDeactivate = new Button { Text = "Delete scheme", AutoSize = true };
            btnDeactivate.Click += OnDeactivateScheme;
            _validationResultLabel = new Label { AutoSize = true, Text = "" };
            schemeActions.Controls.Add(btnValidate);
            schemeActions.Controls.Add(btnSaveScheme);
            schemeActions.Controls.Add(btnDeactivate);
            schemeActions.Controls.Add(_validationResultLabel);
            AddSection(panel, CreateGroupBox("Scheme actions", schemeActions));

            return panel;
        }

        private TabPage BuildConfigTab()
        {
            var page = CreateTabPage("Configuration");
            var panel = CreateTabPanel();
            page.Controls.Add(panel);

            var connectionLayout = CreateFormLayout();
            _deliverablesFolderText = new TextBox { Width = 220 };
            AddField(connectionLayout, "Output folder", CreateFolderPicker(_deliverablesFolderText, OnBrowseDeliverables));
            _quickBackendUrlText = new TextBox { Width = 220 };
            AddField(connectionLayout, "Backend URL", _quickBackendUrlText);
            _quickAuthTokenText = new TextBox { Width = 220, UseSystemPasswordChar = true };
            AddField(connectionLayout, "Auth token", _quickAuthTokenText);

            var connectionWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            connectionWrap.Controls.Add(connectionLayout);
            connectionWrap.Controls.Add(new Label
            {
                Text = "Use the public TinyMRP origin and a raw API token. Templates and advanced defaults stay installed automatically.",
                AutoSize = true,
                ForeColor = SystemColors.GrayText,
                MaximumSize = new Size(520, 0)
            });
            AddSection(panel, CreateGroupBox("Connection", connectionWrap));

            var actions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            var btnSave = new Button { Text = "Save settings", AutoSize = true };
            btnSave.Click += OnQuickSaveSettings;
            var btnTest = new Button { Text = "Test connection", AutoSize = true };
            btnTest.Click += OnQuickTestConnection;
            var btnDefaults = new Button { Text = "Apply server defaults", AutoSize = true };
            btnDefaults.Click += OnQuickApplyDefaults;
            _quickDiagnosticsButton = new Button { Text = "Diagnostics", AutoSize = true };
            _quickDiagnosticsButton.Click += OnQuickDiagnostics;
            _configPathLabel = new Label { AutoSize = true };
            actions.Controls.Add(btnSave);
            actions.Controls.Add(btnTest);
            actions.Controls.Add(btnDefaults);
            actions.Controls.Add(_quickDiagnosticsButton);
            actions.Controls.Add(_configPathLabel);
            AddSection(panel, CreateGroupBox("Actions", actions));

            WireQuickStartSyncEvents();
            return page;
        }

        private TabPage BuildConfigQuickStartTab()
        {
            var page = CreateTabPage("Quick Start");
            var panel = CreateTabPanel();
            page.Controls.Add(panel);

            var connectionLayout = CreateFormLayout();
            _quickBackendUrlText = new TextBox { Width = 220 };
            AddField(connectionLayout, "Backend URL", _quickBackendUrlText);
            _quickAuthTokenText = new TextBox { Width = 220, UseSystemPasswordChar = true };
            AddField(connectionLayout, "Auth token", _quickAuthTokenText);
            AddSection(panel, CreateGroupBox("Connection", connectionLayout));

            var schemeLayout = CreateFormLayout();
            _quickSchemeCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 220 };
            _quickRefreshSchemesButton = new Button { Text = "Refresh", AutoSize = true };
            _quickRefreshSchemesButton.Click += OnQuickRefreshSchemes;
            AddField(schemeLayout, "Numbering scheme", CreateInlineField(_quickSchemeCombo, _quickRefreshSchemesButton));
            AddSection(panel, CreateGroupBox("Numbering scheme", schemeLayout));

            var defaultsLayout = CreateFormLayout();
            _quickApplyModeCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 220 };
            _quickApplyModeCombo.Items.AddRange(new object[] { "Active configuration", "All configurations", "Selected configurations" });
            AddField(defaultsLayout, "Apply mode", _quickApplyModeCombo);
            _quickPartNumberPropText = new TextBox { Width = 200 };
            AddField(defaultsLayout, "Part number property", _quickPartNumberPropText);
            _quickRevisionPropText = new TextBox { Width = 200 };
            AddField(defaultsLayout, "Revision property", _quickRevisionPropText);
            _quickDisplayCodePropText = new TextBox { Width = 200 };
            AddField(defaultsLayout, "Display code property", _quickDisplayCodePropText);
            AddSection(panel, CreateGroupBox("Numbering defaults", defaultsLayout));

            var paths = CreateFormLayout();
            _deliverablesFolderText = new TextBox { Width = 200 };
            AddField(paths, "Output folder", CreateFolderPicker(_deliverablesFolderText, OnBrowseDeliverables));
            var pathNote = new Label
            {
                Text = "Used for deliverables and BOM output.",
                AutoSize = true,
                ForeColor = SystemColors.GrayText,
                Padding = new Padding(0, 4, 0, 0)
            };
            var pathWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            pathWrap.Controls.Add(paths);
            pathWrap.Controls.Add(pathNote);
            AddSection(panel, CreateGroupBox("Paths", pathWrap));

            var actions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false
            };
            var btnSave = new Button { Text = "Save settings", AutoSize = true };
            btnSave.Click += OnQuickSaveSettings;
            actions.Controls.Add(btnSave);
            var actionWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            actionWrap.Controls.Add(actions);
            AddSection(panel, CreateGroupBox("Actions", actionWrap));

            WireQuickStartSyncEvents();
            return page;
        }

        private TabPage BuildConfigAdvancedTab()
        {
            var page = CreateTabPage("Advanced");
            var panel = CreateTabPanel();
            page.Controls.Add(panel);

            var templates = CreateFormLayout();
            _blankTemplateText = new TextBox { Width = 200 };
            AddField(templates, "DXF template", CreateFilePicker(_blankTemplateText, OnBrowseBlankTemplate));
            _bomTemplateText = new TextBox { Width = 200 };
            AddField(templates, "BOM template", CreateFilePicker(_bomTemplateText, OnBrowseBomTemplate));
            AddSection(panel, CreateGroupBox("Templates", templates));

            var drawingExport = CreateFormLayout();
            _dxfSheetNamesText = new TextBox { Width = 200 };
            AddField(drawingExport, "DXF sheet names", _dxfSheetNamesText);
            AddSection(panel, CreateGroupBox("Drawing export", drawingExport));

            var web = CreateFormLayout();
            _weblinkText = new TextBox { Width = 200 };
            var openWeb = new Button { Text = "Open", AutoSize = true };
            openWeb.Click += OnOpenWeb;
            AddField(web, "Web", CreateInlineField(_weblinkText, openWeb));
            _backendUrlText = new TextBox { Width = 200 };
            AddField(web, "Backend URL", _backendUrlText);
            _authTokenText = new TextBox { Width = 200, UseSystemPasswordChar = true };
            AddField(web, "Auth token", _authTokenText);
            var serverNote = new Label
            {
                Text = "Auth token is required for protected APIs (numbering).",
                AutoSize = true,
                ForeColor = SystemColors.GrayText,
                Padding = new Padding(0, 4, 0, 0)
            };
            var serverWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            serverWrap.Controls.Add(web);
            serverWrap.Controls.Add(serverNote);
            AddSection(panel, CreateGroupBox("Server", serverWrap));

            var quickActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            var btnTest = new Button { Text = "Test connection", AutoSize = true };
            btnTest.Click += OnQuickTestConnection;
            var btnDefaults = new Button { Text = "Apply server defaults", AutoSize = true };
            btnDefaults.Click += OnQuickApplyDefaults;
            var btnPreview = new Button { Text = "Preview next", AutoSize = true };
            btnPreview.Click += OnQuickPreview;
            var btnGoNumbering = new Button { Text = "Go to Numbering", AutoSize = true };
            btnGoNumbering.Click += OnQuickGoToNumbering;
            _quickDiagnosticsButton = new Button { Text = "Diagnostics", AutoSize = true };
            _quickDiagnosticsButton.Click += OnQuickDiagnostics;
            _quickPreviewLabel = new Label { AutoSize = true, Text = "" };
            quickActions.Controls.Add(btnTest);
            quickActions.Controls.Add(btnDefaults);
            quickActions.Controls.Add(btnPreview);
            quickActions.Controls.Add(btnGoNumbering);
            quickActions.Controls.Add(_quickDiagnosticsButton);
            quickActions.Controls.Add(_quickPreviewLabel);
            AddSection(panel, CreateGroupBox("Quick actions", quickActions));

            var defaultsLayout = CreateFormLayout();
            _advancedSchemeCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 220 };
            AddField(defaultsLayout, "Default scheme", _advancedSchemeCombo);
            _advancedApplyModeCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 220 };
            _advancedApplyModeCombo.Items.AddRange(new object[] { "Active configuration", "All configurations", "Selected configurations" });
            AddField(defaultsLayout, "Apply mode", _advancedApplyModeCombo);
            _partNumberPropText = new TextBox { Width = 200 };
            AddField(defaultsLayout, "Part number property", _partNumberPropText);
            _revisionPropText = new TextBox { Width = 200 };
            AddField(defaultsLayout, "Revision property", _revisionPropText);
            _displayCodePropText = new TextBox { Width = 200 };
            AddField(defaultsLayout, "Display code property", _displayCodePropText);
            _advancedContextJsonText = new TextBox { Width = 200, Multiline = true, Height = 80, ScrollBars = ScrollBars.Vertical };
            AddField(defaultsLayout, "Context JSON", _advancedContextJsonText);
            AddSection(panel, CreateGroupBox("Server defaults", defaultsLayout));

            _removeModifiedNotesCheck = CreateCheckBox("Remove modified notes");
            AddSection(panel, CreateGroupBox("Options", _removeModifiedNotesCheck));

            var numberingAdvancedWrap = CreateStackPanel();

            var renameWrap = CreateStackPanel();
            _renameAutoCheck = CreateCheckBox("Auto-rename file after allocation");
            _renameModeCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 220 };
            _renameModeCombo.Items.AddRange(new object[] { "Safe (recommended)", "Rename only if not referenced" });
            _renameAppendRevisionCheck = CreateCheckBox("Append revision to filename");
            _renameKeepBackupCheck = CreateCheckBox("Keep original file as backup");
            _renameKeepBackupCheck.Checked = true;
            AddStackRow(renameWrap, _renameAutoCheck);
            AddStackRow(renameWrap, _renameModeCombo);
            AddStackRow(renameWrap, _renameAppendRevisionCheck);
            AddStackRow(renameWrap, _renameKeepBackupCheck);
            AddStackRow(numberingAdvancedWrap, CreateGroupBox("Rename options", renameWrap));

            var autoAssignWrap = CreateStackPanel();
            _autoAssignGenericCheck = CreateCheckBox("Auto-assign for Part1/Assembly1 names");
            _autoAssignGenericCheck.CheckedChanged += (_, __) => MaybeAutoAssignNumbering(true);
            AddStackRow(autoAssignWrap, _autoAssignGenericCheck);
            AddStackRow(numberingAdvancedWrap, CreateGroupBox("Auto-assign", autoAssignWrap));

            var numberingAdvancedPanel = BuildNumberingAdvancedPanel();
            AddStackRow(numberingAdvancedWrap, CreateCollapsibleSection("Numbering editor", numberingAdvancedPanel, false));
            AddSection(panel, CreateGroupBox("Numbering (Advanced)", numberingAdvancedWrap));

            var configActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            var btnSaveLocal = new Button { Text = "Save local config", AutoSize = true };
            btnSaveLocal.Click += OnSaveConfig;
            var btnSaveServer = new Button { Text = "Save server settings", AutoSize = true };
            btnSaveServer.Click += OnAdvancedSaveSettings;
            _configPathLabel = new Label { AutoSize = true };
            configActions.Controls.Add(btnSaveLocal);
            configActions.Controls.Add(btnSaveServer);
            configActions.Controls.Add(_configPathLabel);
            AddSection(panel, CreateGroupBox("Config", configActions));

            WireAdvancedSyncEvents();
            return page;
        }

        private void WireQuickStartSyncEvents()
        {
            if (_quickBackendUrlText != null)
            {
                _quickBackendUrlText.TextChanged += (_, __) => SyncText(_quickBackendUrlText, _backendUrlText);
            }
            if (_quickAuthTokenText != null)
            {
                _quickAuthTokenText.TextChanged += (_, __) => SyncText(_quickAuthTokenText, _authTokenText);
            }
            if (_quickPartNumberPropText != null)
            {
                _quickPartNumberPropText.TextChanged += (_, __) => SyncText(_quickPartNumberPropText, _partNumberPropText);
                _quickPartNumberPropText.TextChanged += (_, __) => SyncText(_quickPartNumberPropText, _numberingPartNumberPropText);
            }
            if (_quickRevisionPropText != null)
            {
                _quickRevisionPropText.TextChanged += (_, __) => SyncText(_quickRevisionPropText, _revisionPropText);
                _quickRevisionPropText.TextChanged += (_, __) => SyncText(_quickRevisionPropText, _numberingRevisionPropText);
            }
            if (_quickDisplayCodePropText != null)
            {
                _quickDisplayCodePropText.TextChanged += (_, __) => SyncText(_quickDisplayCodePropText, _displayCodePropText);
                _quickDisplayCodePropText.TextChanged += (_, __) => SyncText(_quickDisplayCodePropText, _numberingDisplayCodePropText);
            }
            if (_quickApplyModeCombo != null)
            {
                _quickApplyModeCombo.SelectedIndexChanged += (_, __) =>
                {
                    SyncCombo(_quickApplyModeCombo, _advancedApplyModeCombo);
                    SelectApplyModeCombo(_applyScopeCombo, ApplyModeFromCombo(_quickApplyModeCombo));
                };
            }
            if (_quickSchemeCombo != null)
            {
                _quickSchemeCombo.SelectedIndexChanged += OnQuickSchemeSelected;
            }
        }

        private void WireAdvancedSyncEvents()
        {
            if (_backendUrlText != null)
            {
                _backendUrlText.TextChanged += (_, __) => SyncText(_backendUrlText, _quickBackendUrlText);
            }
            if (_authTokenText != null)
            {
                _authTokenText.TextChanged += (_, __) => SyncText(_authTokenText, _quickAuthTokenText);
            }
            if (_partNumberPropText != null)
            {
                _partNumberPropText.TextChanged += (_, __) => SyncText(_partNumberPropText, _quickPartNumberPropText);
                _partNumberPropText.TextChanged += (_, __) => SyncText(_partNumberPropText, _numberingPartNumberPropText);
            }
            if (_numberingPartNumberPropText != null)
            {
                _numberingPartNumberPropText.TextChanged += (_, __) => SyncText(_numberingPartNumberPropText, _partNumberPropText);
            }
            if (_revisionPropText != null)
            {
                _revisionPropText.TextChanged += (_, __) => SyncText(_revisionPropText, _quickRevisionPropText);
                _revisionPropText.TextChanged += (_, __) => SyncText(_revisionPropText, _numberingRevisionPropText);
            }
            if (_numberingRevisionPropText != null)
            {
                _numberingRevisionPropText.TextChanged += (_, __) => SyncText(_numberingRevisionPropText, _revisionPropText);
            }
            if (_displayCodePropText != null)
            {
                _displayCodePropText.TextChanged += (_, __) => SyncText(_displayCodePropText, _quickDisplayCodePropText);
                _displayCodePropText.TextChanged += (_, __) => SyncText(_displayCodePropText, _numberingDisplayCodePropText);
            }
            if (_numberingDisplayCodePropText != null)
            {
                _numberingDisplayCodePropText.TextChanged += (_, __) => SyncText(_numberingDisplayCodePropText, _displayCodePropText);
            }
            if (_advancedApplyModeCombo != null)
            {
                _advancedApplyModeCombo.SelectedIndexChanged += (_, __) =>
                {
                    SyncCombo(_advancedApplyModeCombo, _quickApplyModeCombo);
                    SelectApplyModeCombo(_applyScopeCombo, ApplyModeFromCombo(_advancedApplyModeCombo));
                };
            }
            if (_advancedSchemeCombo != null)
            {
                _advancedSchemeCombo.SelectedIndexChanged += (_, __) => SyncSchemeSelection(_advancedSchemeCombo, _quickSchemeCombo);
                _advancedSchemeCombo.SelectedIndexChanged += (_, __) => SyncSchemeSelection(_advancedSchemeCombo, _numberingPresetCombo);
            }
        }

        private void SyncText(TextBox source, TextBox target)
        {
            if (source == null || target == null || _syncingConfigFields)
            {
                return;
            }

            try
            {
                _syncingConfigFields = true;
                target.Text = source.Text;
            }
            finally
            {
                _syncingConfigFields = false;
            }
        }

        private void SyncCombo(ComboBox source, ComboBox target)
        {
            if (source == null || target == null || _syncingConfigFields)
            {
                return;
            }

            try
            {
                _syncingConfigFields = true;
                target.SelectedIndex = source.SelectedIndex;
            }
            finally
            {
                _syncingConfigFields = false;
            }
        }

        private void SyncSchemeSelection(ComboBox source, ComboBox target)
        {
            if (source == null || target == null || _syncingConfigFields)
            {
                return;
            }

            NumberingSchemeDefinition scheme = source.SelectedItem as NumberingSchemeDefinition;
            if (scheme == null)
            {
                return;
            }

            try
            {
                _syncingConfigFields = true;
                SelectComboItem(target, scheme.Id);
                if (_schemeCombo != null)
                {
                    SelectComboItem(_schemeCombo, scheme.Id);
                }
            }
            finally
            {
                _syncingConfigFields = false;
            }
        }

        private void OnQuickSchemeSelected(object sender, EventArgs e)
        {
            NumberingSchemeDefinition scheme = _quickSchemeCombo != null
                ? _quickSchemeCombo.SelectedItem as NumberingSchemeDefinition
                : null;
            UpdateQuickContextVisibility(scheme);
            if (scheme != null)
            {
                SyncSchemeSelection(_quickSchemeCombo, _advancedSchemeCombo);
                SyncSchemeSelection(_quickSchemeCombo, _numberingPresetCombo);
            }
        }

        private void UpdateQuickContextVisibility(NumberingSchemeDefinition scheme)
        {
            UpdateContextVisibility(_quickContextRows, scheme);
            UpdateContextVisibility(_numberingContextRows, scheme);
            UpdateSequenceOverridePanel(scheme);
        }

        private void UpdateContextVisibility(Dictionary<string, Control[]> rows, NumberingSchemeDefinition scheme)
        {
            if (rows == null || rows.Count == 0)
            {
                return;
            }

            var required = GetRequiredContextKeys(scheme);
            foreach (var pair in rows)
            {
                bool visible = required.Count == 0 || required.Contains(pair.Key);
                foreach (Control control in pair.Value)
                {
                    if (control != null)
                    {
                        control.Visible = visible;
                    }
                }
            }
        }

        private HashSet<string> GetRequiredContextKeys(NumberingSchemeDefinition scheme)
        {
            var required = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (scheme == null)
            {
                return required;
            }

            foreach (NumberingSegmentDefinition segment in scheme.PatternSegments)
            {
                if (segment != null && string.Equals(segment.Kind, "field", StringComparison.OrdinalIgnoreCase))
                {
                    string field = segment.Field;
                    if (!string.IsNullOrWhiteSpace(field))
                    {
                        required.Add(field.Trim());
                    }
                }
            }

            string scope = scheme.ScopeMode ?? string.Empty;
            if (scope.Equals("by_type", StringComparison.OrdinalIgnoreCase))
            {
                required.Add("type");
            }
            else if (scope.Equals("by_family", StringComparison.OrdinalIgnoreCase))
            {
                required.Add("family");
            }
            else if (scope.Equals("by_project", StringComparison.OrdinalIgnoreCase))
            {
                required.Add("project");
            }
            else if (scope.Equals("custom_keys", StringComparison.OrdinalIgnoreCase))
            {
                foreach (string key in scheme.ScopeKeys)
                {
                    if (!string.IsNullOrWhiteSpace(key))
                    {
                        required.Add(key.Trim());
                    }
                }
            }

            return required;
        }

        private void UpdateSequenceOverridePanel(NumberingSchemeDefinition scheme)
        {
            if (_numberingSeqOverridePanel == null)
            {
                return;
            }

            _numberingSeqOverridePanel.SuspendLayout();
            _numberingSeqOverridePanel.Controls.Clear();
            _numberingSeqOverrides.Clear();

            int seqCount = CountSequenceSegments(scheme);
            if (seqCount <= 0)
            {
                _numberingSeqOverridePanel.Visible = false;
                if (_numberingSeqOverrideGroup != null)
                {
                    _numberingSeqOverrideGroup.Visible = false;
                }
                _numberingSeqOverridePanel.ResumeLayout();
                return;
            }

            _numberingSeqOverridePanel.Visible = true;
            if (_numberingSeqOverrideGroup != null)
            {
                _numberingSeqOverrideGroup.Visible = true;
            }
            List<NumberingSegmentDefinition> sequenceSegments = GetSequenceSegments(scheme);
            int autoSequenceIndex = GetAutomaticSequenceIndex(scheme);
            List<int> rememberedValues = GetStoredSequenceOverrideValues(scheme);

            for (int i = 0; i < seqCount; i++)
            {
                NumberingSegmentDefinition sequenceSegment = i < sequenceSegments.Count ? sequenceSegments[i] : null;
                bool isAutomatic = i == autoSequenceIndex || (autoSequenceIndex < 0 && seqCount == 1);
                int startAt = rememberedValues != null && i < rememberedValues.Count && rememberedValues[i] > 0
                    ? rememberedValues[i]
                    : GetSequenceStartValue(scheme, sequenceSegment, isAutomatic);
                var row = new TableLayoutPanel
                {
                    ColumnCount = 2,
                    AutoSize = true,
                    AutoSizeMode = AutoSizeMode.GrowAndShrink,
                    Dock = DockStyle.Top
                };
                row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 60F));
                row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 40F));

                var label = new Label
                {
                    Text = seqCount > 1
                        ? string.Format("Sequence {0} {1}", i + 1, isAutomatic ? "(Auto)" : "(Manual)")
                        : "Sequence start",
                    AutoSize = true,
                    Anchor = AnchorStyles.Left
                };
                var upDown = new NumericUpDown
                {
                    Minimum = 1,
                    Maximum = 999999,
                    Width = 120,
                    Value = startAt,
                    Anchor = AnchorStyles.Left
                };
                upDown.ValueChanged += (_, __) =>
                {
                    if (isAutomatic && _seqStartUpDown != null)
                    {
                        _seqStartUpDown.Value = upDown.Value;
                    }

                    RememberCurrentSequenceOverrides(scheme);
                };
                row.Controls.Add(label, 0, 0);
                row.Controls.Add(upDown, 1, 0);

                _numberingSeqOverridePanel.Controls.Add(row);
                _numberingSeqOverrides.Add(upDown);
            }

            if (_numberingSeqOverrideNote != null)
            {
                _numberingSeqOverrideNote.Text = "Auto sequence uses this as the next minimum value. Manual sequences use these values for the current run.";
                _numberingSeqOverridePanel.Controls.Add(_numberingSeqOverrideNote);
            }

            RememberCurrentSequenceOverrides(scheme);
            _numberingSeqOverridePanel.ResumeLayout();
        }

        private int CountSequenceSegments(NumberingSchemeDefinition scheme)
        {
            return GetSequenceSegments(scheme).Count;
        }

        private List<NumberingSegmentDefinition> GetSequenceSegments(NumberingSchemeDefinition scheme)
        {
            var segments = new List<NumberingSegmentDefinition>();
            if (scheme == null || scheme.PatternSegments == null)
            {
                return segments;
            }

            foreach (NumberingSegmentDefinition segment in scheme.PatternSegments)
            {
                if (segment != null && string.Equals(segment.Kind, "seq", StringComparison.OrdinalIgnoreCase))
                {
                    segments.Add(segment);
                }
            }

            return segments;
        }

        private int GetAutomaticSequenceIndex(NumberingSchemeDefinition scheme)
        {
            List<NumberingSegmentDefinition> sequenceSegments = GetSequenceSegments(scheme);
            if (sequenceSegments.Count == 0)
            {
                return -1;
            }

            if (sequenceSegments.Count == 1)
            {
                return 0;
            }

            int found = -1;
            for (int i = 0; i < sequenceSegments.Count; i++)
            {
                if (!sequenceSegments[i].AutoCounter)
                {
                    continue;
                }

                if (found >= 0)
                {
                    return -1;
                }

                found = i;
            }

            return found;
        }

        private int GetSequenceStartValue(NumberingSchemeDefinition scheme, NumberingSegmentDefinition segment, bool isAutomatic)
        {
            int fallback = scheme != null && scheme.Seq != null ? scheme.Seq.StartAt : 1;
            if (isAutomatic)
            {
                return fallback;
            }

            if (segment != null && segment.StartAt.HasValue && segment.StartAt.Value > 0)
            {
                return segment.StartAt.Value;
            }

            return fallback;
        }

        private List<int> GetStoredSequenceOverrideValues(NumberingSchemeDefinition scheme)
        {
            string key = GetSequenceOverrideKey(scheme);
            if (string.IsNullOrWhiteSpace(key))
            {
                return null;
            }

            if (!_sequenceOverrideCache.TryGetValue(key, out List<int> values) || values == null || values.Count == 0)
            {
                return null;
            }

            return new List<int>(values);
        }

        private void RememberCurrentSequenceOverrides(NumberingSchemeDefinition scheme)
        {
            RememberSequenceOverrideValues(scheme, BuildSequenceOverrideValues(scheme));
        }

        private void RememberSequenceOverrideValues(NumberingSchemeDefinition scheme, List<int> values)
        {
            string key = GetSequenceOverrideKey(scheme);
            if (string.IsNullOrWhiteSpace(key))
            {
                return;
            }

            if (values == null || values.Count == 0)
            {
                _sequenceOverrideCache.Remove(key);
                return;
            }

            _sequenceOverrideCache[key] = new List<int>(values);
        }

        private string GetSequenceOverrideKey(NumberingSchemeDefinition scheme)
        {
            if (scheme == null)
            {
                return string.Empty;
            }

            if (!string.IsNullOrWhiteSpace(scheme.Id))
            {
                return scheme.Id.Trim();
            }

            if (!string.IsNullOrWhiteSpace(scheme.Name))
            {
                return "name:" + scheme.Name.Trim();
            }

            return string.Empty;
        }

        private void ApplySequenceOverrideStateFromResponse(NumberingSchemeDefinition scheme, ApiResponse response, bool useNextValueAfter)
        {
            if (scheme == null || response == null || response.Data == null || _numberingSeqOverrides.Count == 0)
            {
                return;
            }

            List<int> values = ParseSequenceValuesFromResponse(response);
            if (values.Count == 0)
            {
                return;
            }

            int autoSequenceIndex = NumberingJson.GetInt(response.Data, "auto_sequence_index", GetAutomaticSequenceIndex(scheme));
            if (useNextValueAfter && autoSequenceIndex >= 0 && autoSequenceIndex < values.Count)
            {
                int nextValueAfter = NumberingJson.GetInt(response.Data, "next_value_after", 0);
                if (nextValueAfter > 0)
                {
                    values[autoSequenceIndex] = nextValueAfter;
                }
            }

            ApplySequenceOverrideValuesToUi(scheme, values, autoSequenceIndex);
        }

        private List<int> ParseSequenceValuesFromResponse(ApiResponse response)
        {
            var values = new List<int>();
            if (response == null || response.Data == null || !response.Data.ContainsKey("sequence_values_used"))
            {
                return values;
            }

            foreach (object item in NumberingJson.AsList(response.Data["sequence_values_used"]))
            {
                int parsed;
                if (item != null && int.TryParse(item.ToString(), out parsed))
                {
                    values.Add(Math.Max(1, parsed));
                }
            }

            return values;
        }

        private void ApplySequenceOverrideValuesToUi(NumberingSchemeDefinition scheme, List<int> values, int autoSequenceIndex)
        {
            if (scheme == null || values == null || values.Count == 0 || _numberingSeqOverrides.Count == 0)
            {
                return;
            }

            int count = Math.Min(values.Count, _numberingSeqOverrides.Count);
            for (int i = 0; i < count; i++)
            {
                NumericUpDown upDown = _numberingSeqOverrides[i];
                decimal nextValue = ClampNumericValue(upDown, values[i]);
                if (upDown.Value != nextValue)
                {
                    upDown.Value = nextValue;
                }
            }

            if (_seqStartUpDown != null && autoSequenceIndex >= 0 && autoSequenceIndex < count)
            {
                decimal autoValue = ClampNumericValue(_seqStartUpDown, values[autoSequenceIndex]);
                if (_seqStartUpDown.Value != autoValue)
                {
                    _seqStartUpDown.Value = autoValue;
                }
            }

            RememberSequenceOverrideValues(scheme, values);
        }

        private decimal ClampNumericValue(NumericUpDown control, int value)
        {
            if (control == null)
            {
                return Math.Max(1, value);
            }

            decimal nextValue = Math.Max(1, value);
            if (nextValue < control.Minimum)
            {
                return control.Minimum;
            }

            if (nextValue > control.Maximum)
            {
                return control.Maximum;
            }

            return nextValue;
        }

        private string GetPreferredText(TextBox primary, TextBox fallback)
        {
            return GetPreferredText(primary, fallback, string.Empty);
        }

        private string GetPreferredText(TextBox primary, TextBox fallback, string fallbackValue)
        {
            if (primary != null)
            {
                string value = primary.Text != null ? primary.Text.Trim() : string.Empty;
                if (!string.IsNullOrWhiteSpace(value))
                {
                    return value;
                }
            }
            if (fallback != null)
            {
                string value = fallback.Text != null ? fallback.Text.Trim() : string.Empty;
                if (!string.IsNullOrWhiteSpace(value))
                {
                    return value;
                }
            }
            return fallbackValue ?? string.Empty;
        }

        private void SelectApplyModeCombo(ComboBox combo, string applyMode)
        {
            if (combo == null)
            {
                return;
            }
            string label = ApplyModeToLabel(applyMode);
            SelectComboItem(combo, label);
        }

        private string ApplyModeFromCombo(ComboBox combo)
        {
            return LabelToApplyMode(GetComboText(combo));
        }

        private string ApplyModeToLabel(string applyMode)
        {
            string mode = (applyMode ?? string.Empty).Trim().ToLowerInvariant();
            if (mode == "all_configs")
            {
                return "All configurations";
            }
            if (mode == "selected_configs")
            {
                return "Selected configurations";
            }
            return "Active configuration";
        }

        private string LabelToApplyMode(string label)
        {
            if (label == null)
            {
                return "active_config";
            }
            if (label.StartsWith("All", StringComparison.OrdinalIgnoreCase))
            {
                return "all_configs";
            }
            if (label.StartsWith("Selected", StringComparison.OrdinalIgnoreCase))
            {
                return "selected_configs";
            }
            return "active_config";
        }

        private string GetDefaultSchemeId()
        {
            string numbering = GetSchemeIdFromCombo(_numberingPresetCombo);
            if (!string.IsNullOrWhiteSpace(numbering))
            {
                return numbering;
            }
            string quick = GetSchemeIdFromCombo(_quickSchemeCombo);
            if (!string.IsNullOrWhiteSpace(quick))
            {
                return quick;
            }
            string advanced = GetSchemeIdFromCombo(_advancedSchemeCombo);
            if (!string.IsNullOrWhiteSpace(advanced))
            {
                return advanced;
            }
            return GetSelectedSchemeId();
        }

        private string GetSchemeIdFromCombo(ComboBox combo)
        {
            NumberingSchemeDefinition scheme = combo != null ? combo.SelectedItem as NumberingSchemeDefinition : null;
            if (scheme != null && !string.IsNullOrWhiteSpace(scheme.Id))
            {
                return scheme.Id;
            }
            if (combo != null && combo.Items.Count == 0 && combo.Tag is string tagValue)
            {
                return tagValue;
            }
            return string.Empty;
        }

        private string ContextToJson(Dictionary<string, string> context)
        {
            var serializer = new System.Web.Script.Serialization.JavaScriptSerializer();
            return serializer.Serialize(context ?? new Dictionary<string, string>());
        }

        private bool TryParseContextJson(string json, out Dictionary<string, string> context, out string error)
        {
            context = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            error = null;
            if (string.IsNullOrWhiteSpace(json))
            {
                return true;
            }

            try
            {
                var serializer = new System.Web.Script.Serialization.JavaScriptSerializer();
                var parsed = serializer.DeserializeObject(json) as Dictionary<string, object>;
                if (parsed == null)
                {
                    error = "Context JSON must be an object.";
                    return false;
                }
                foreach (var pair in parsed)
                {
                    if (pair.Key == null)
                    {
                        continue;
                    }
                    context[pair.Key] = pair.Value != null ? pair.Value.ToString() : string.Empty;
                }
                return true;
            }
            catch (Exception ex)
            {
                error = ex.Message;
                return false;
            }
        }

        private void ApplyConfig(TinyMrpConfig config)
        {
            if (config == null)
            {
                return;
            }

            if (_deliverablesFolderText != null)
            {
                string folder = config.DeliverablesFolder;
                if (string.IsNullOrWhiteSpace(folder))
                {
                    folder = config.BomFolder;
                }
                _deliverablesFolderText.Text = folder;
            }

            if (_weblinkText != null)
            {
                _weblinkText.Text = config.WebLink;
            }

            if (_backendUrlText != null)
            {
                _backendUrlText.Text = string.IsNullOrWhiteSpace(config.BackendUrl) ? config.WebLink : config.BackendUrl;
            }
            if (_quickBackendUrlText != null)
            {
                _quickBackendUrlText.Text = string.IsNullOrWhiteSpace(config.BackendUrl) ? config.WebLink : config.BackendUrl;
            }

            if (_authTokenText != null)
            {
                _authTokenText.Text = config.AuthToken ?? string.Empty;
            }
            if (_quickAuthTokenText != null)
            {
                _quickAuthTokenText.Text = config.AuthToken ?? string.Empty;
            }

            if (_bomTemplateText != null)
            {
                _bomTemplateText.Text = config.BomTemplatePath;
            }

            if (_blankTemplateText != null)
            {
                _blankTemplateText.Text = config.BlankTemplatePath;
            }

            if (_dxfSheetNamesText != null)
            {
                _dxfSheetNamesText.Text = config.DxfSheetNames ?? string.Empty;
            }

            if (_removeModifiedNotesCheck != null)
            {
                _removeModifiedNotesCheck.Checked = config.RemoveModifiedNotes;
            }

            if (_configPathLabel != null)
            {
                _configPathLabel.Text = "Config: " + config.ConfigPath;
            }

            ApplyNumberingDefaults(config);
        }

        private PublishOptions BuildOptions()
        {
            UpdateConfigFromUi();

            var options = new PublishOptions
            {
                DeliverablesFolder = _deliverablesFolderText != null ? _deliverablesFolderText.Text : string.Empty,
                BomFolder = _deliverablesFolderText != null ? _deliverablesFolderText.Text : string.Empty,
                ExportPngModel = _pngModelCheck != null && _pngModelCheck.Checked,
                ExportStep = _stepCheck != null && _stepCheck.Checked,
                ExportEdrawing = _edrCheck != null && _edrCheck.Checked,
                Export3mf = _threeMfCheck != null && _threeMfCheck.Checked,
                ExportPly = _plyCheck != null && _plyCheck.Checked,
                ExportStl = _stlCheck != null && _stlCheck.Checked,
                ExportPngDrawing = _pngDrawingCheck != null && _pngDrawingCheck.Checked,
                ExportPdf = _pdfCheck != null && _pdfCheck.Checked,
                ExportDxf = _dxfCheck != null && _dxfCheck.Checked,
                ExportEdrawingDrawing = _edrDrawingCheck != null && _edrDrawingCheck.Checked,
                OverwriteFiles = _overwriteCheck != null && _overwriteCheck.Checked,
                TopLevelOnly = _topLevelOnlyCheck != null && _topLevelOnlyCheck.Checked,
                CreateUploadPack = false
            };

            return options;
        }

        private PublishOptions BuildUploadPackOptions()
        {
            PublishOptions options = BuildOptions();
            options.CreateUploadPack = true;
            options.UploadPackIncludeDeliverables = _uploadPackIncludeDeliverablesCheck != null &&
                _uploadPackIncludeDeliverablesCheck.Checked;
            options.UploadPackIncludeExtras = _uploadPackIncludeExtrasCheck != null &&
                _uploadPackIncludeExtrasCheck.Checked;
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

            config.BomFolder = config.DeliverablesFolder;

            if (_weblinkText != null)
            {
                config.WebLink = _weblinkText.Text;
            }

            if (_quickBackendUrlText != null || _backendUrlText != null)
            {
                config.BackendUrl = GetPreferredText(_quickBackendUrlText, _backendUrlText);
            }

            if (_quickAuthTokenText != null || _authTokenText != null)
            {
                config.AuthToken = GetPreferredText(_quickAuthTokenText, _authTokenText);
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

            if (_dxfSheetNamesText != null)
            {
                config.DxfSheetNames = _dxfSheetNamesText.Text;
            }

            string schemeId = GetDefaultSchemeId();
            if (!string.IsNullOrWhiteSpace(schemeId))
            {
                config.NumberingSchemeId = schemeId;
            }

            config.NumberingContextDefaults = string.Empty;
            config.PartNumberProperty = GetPreferredText(
                _quickPartNumberPropText ?? _numberingPartNumberPropText,
                _partNumberPropText,
                config.PartNumberProperty ?? "PartNumber");
            config.RevisionProperty = GetPreferredText(
                _quickRevisionPropText ?? _numberingRevisionPropText,
                _revisionPropText,
                config.RevisionProperty ?? "Revision");
            config.DisplayCodeProperty = GetPreferredText(
                _quickDisplayCodePropText ?? _numberingDisplayCodePropText,
                _displayCodePropText,
                config.DisplayCodeProperty ?? "DisplayCode");
            config.NumberingApplyMode = ApplyModeFromCombo(_quickApplyModeCombo ?? _advancedApplyModeCombo ?? _applyScopeCombo);
            config.AutoAssignGenericNames = _autoAssignGenericCheck != null && _autoAssignGenericCheck.Checked;
            config.AutoAssignAnyNames = _autoAssignAnyNameCheck != null && _autoAssignAnyNameCheck.Checked;
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
            ResetProgress(_publishProgressBar, _publishProgressLabel, "Create files");
            SetStatus("Creating files...");
            UpdateRunLogLink(string.Empty);
            publisher.ProcessFiles(options, Log, UpdatePublishProgress);
            UpdateRunLogLink(publisher.LastRunLogPath);
            // Keep the final status/progress from the publisher (includes per-run log path).
        }

        private void OnResumeLastExport(object sender, EventArgs e)
        {
            TinyMrpPublisher publisher = AddinContext.Publisher;
            if (publisher == null)
            {
                MessageBox.Show("Publisher is not initialized.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            if (!publisher.HasIncompleteExportSession())
            {
                MessageBox.Show("No incomplete export session was found.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
                return;
            }

            ResetProgress(_publishProgressBar, _publishProgressLabel, "Create files");
            SetStatus("Resuming last export...");
            UpdateRunLogLink(string.Empty);
            try
            {
                publisher.ResumeLastCreateFilesExport(Log, UpdatePublishProgress);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Resume failed: " + ex.Message, "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            UpdateRunLogLink(publisher.LastRunLogPath);
        }

        private void OnCreateUploadPack(object sender, EventArgs e)
        {
            TinyMrpPublisher publisher = AddinContext.Publisher;
            if (publisher == null)
            {
                MessageBox.Show("Publisher is not initialized.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            PublishOptions options = BuildUploadPackOptions();
            SetStatus("Creating upload pack...");
            UpdateRunLogLink(string.Empty);
            publisher.ProcessUploadPack(options, Log);
            UpdateRunLogLink(publisher.LastRunLogPath);
            SetStatus("Done.");
        }

        private void OnManageAssociatedFiles(object sender, EventArgs e)
        {
            ISldWorks app = AddinContext.SldWorks;
            if (app == null)
            {
                MessageBox.Show("SolidWorks not available.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ActiveModelInfo info;
            string error;
            if (!SolidWorksDocumentHelper.TryGetActiveModel(app, out info, out error))
            {
                MessageBox.Show(error ?? "No active model.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string configName = info.ActiveConfiguration;
            if (string.IsNullOrWhiteSpace(configName))
            {
                Configuration activeConfig = info.Model.GetActiveConfiguration() as Configuration;
                configName = activeConfig != null ? activeConfig.Name : string.Empty;
            }

            string raw = GetCustomProperty(info.Model, configName, AssociatedFilesPayload.PropertyName);
            if (string.IsNullOrWhiteSpace(raw))
            {
                raw = GetCustomProperty(info.Model, string.Empty, AssociatedFilesPayload.PropertyName);
            }
            AssociatedFilesPayload payload = AssociatedFilesPayload.FromJson(raw);
            using (var dialog = new AssociatedFilesDialog(payload.Files))
            {
                if (dialog.ShowDialog(this) == DialogResult.OK)
                {
                    payload.Files = dialog.Files ?? new List<AssociatedFileEntry>();
                    string json = payload.ToJson();
                    SolidWorksPropertyWriter.SetCustomProperty(
                        info.Model,
                        configName,
                        AssociatedFilesPayload.PropertyName,
                        json);
                    try
                    {
                        if (!string.IsNullOrWhiteSpace(info.Model.GetPathName()))
                        {
                            info.Model.Save2(true);
                        }
                    }
                    catch
                    {
                        // ignore save errors
                    }
                }
            }

            if (info.StartedFromDrawing)
            {
                app.ActivateDoc(info.StartTitle);
            }
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
            ResetProgress(_bomProgressBar, _bomProgressLabel, "Process BOM");
            SetStatus("Processing BOM...");
            UpdateRunLogLink(string.Empty);
            publisher.ProcessBom(options, Log, UpdateBomProgress);
            UpdateRunLogLink(publisher.LastRunLogPath);
            SetStatus("Done.");
            ResetProgress(_bomProgressBar, _bomProgressLabel, "Process BOM");
        }

        private void OnCancelCurrentTask(object sender, EventArgs e)
        {
            TinyMrpPublisher publisher = AddinContext.Publisher;
            if (publisher == null)
            {
                return;
            }

            publisher.RequestCancel();
            SetStatus("Cancel requested...");
        }

        private void OnStopProcess(object sender, EventArgs e)
        {
            TinyMrpPublisher publisher = AddinContext.Publisher;
            if (publisher == null)
            {
                return;
            }

            publisher.RequestStopAfterCurrentItem();
            SetStatus("Stop requested; finishing current file...");
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

            _toolsActionName = freeze ? "Freeze model" : "Unfreeze model";
            ResetProgress(_toolsProgressBar, _toolsProgressLabel, _toolsActionName);
            SetStatus(freeze ? "Freezing model..." : "Unfreezing model...");
            publisher.FreezeDesign(freeze, Log, UpdateToolsProgress);
            SetStatus("Done.");
            ResetProgress(_toolsProgressBar, _toolsProgressLabel, _toolsActionName);
        }

        private void OnNormalizeUnits(object sender, EventArgs e)
        {
            TinyMrpPublisher publisher = AddinContext.Publisher;
            if (publisher == null)
            {
                MessageBox.Show("Publisher is not initialized.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            _toolsActionName = "Normalize units";
            ResetProgress(_toolsProgressBar, _toolsProgressLabel, _toolsActionName);
            SetStatus("Normalizing units...");
            publisher.NormalizeUnits(Log, UpdateToolsProgress);
            SetStatus("Done.");
            ResetProgress(_toolsProgressBar, _toolsProgressLabel, _toolsActionName);
        }

        private void OnHideFeatures(object sender, EventArgs e)
        {
            TinyMrpPublisher publisher = AddinContext.Publisher;
            if (publisher == null)
            {
                MessageBox.Show("Publisher is not initialized.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            HideFeatureTypeFlags mask = HideFeatureTypeFlags.None;
            if (_hideOriginCheck != null && _hideOriginCheck.Checked) mask |= HideFeatureTypeFlags.Origin;
            if (_hidePlaneCheck != null && _hidePlaneCheck.Checked) mask |= HideFeatureTypeFlags.RefPlane;
            if (_hideAxisCheck != null && _hideAxisCheck.Checked) mask |= HideFeatureTypeFlags.RefAxis;
            if (_hidePointCheck != null && _hidePointCheck.Checked) mask |= HideFeatureTypeFlags.RefPoint;
            if (_hideCoordSysCheck != null && _hideCoordSysCheck.Checked) mask |= HideFeatureTypeFlags.CoordSys;
            if (_hideSketch2DCheck != null && _hideSketch2DCheck.Checked) mask |= HideFeatureTypeFlags.Sketch2D;
            if (_hideSketch3DCheck != null && _hideSketch3DCheck.Checked) mask |= HideFeatureTypeFlags.Sketch3D;
            if (_hideSpline3DCheck != null && _hideSpline3DCheck.Checked) mask |= HideFeatureTypeFlags.Spline3D;
            if (_hideCompositeCurveCheck != null && _hideCompositeCurveCheck.Checked) mask |= HideFeatureTypeFlags.CompositeCurve;
            if (_hideHelixCheck != null && _hideHelixCheck.Checked) mask |= HideFeatureTypeFlags.Helix;

            var options = new HideFeaturesOptions
            {
                FeatureMask = mask,
                AllConfigurations = _hideAllConfigsCheck != null && _hideAllConfigsCheck.Checked,
                HideEnvelopes = _hideEnvelopeCheck != null && _hideEnvelopeCheck.Checked
            };

            _toolsActionName = "Hide features";
            ResetProgress(_toolsProgressBar, _toolsProgressLabel, _toolsActionName);
            SetStatus("Hiding features...");
            publisher.HideFeatures(options, Log, UpdateToolsProgress);
            SetStatus("Done.");
            ResetProgress(_toolsProgressBar, _toolsProgressLabel, _toolsActionName);
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
                _numberingClient = null;
                MessageBox.Show("Config saved.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to save config: " + ex.Message, "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void OnQuickTestConnection(object sender, EventArgs e)
        {
            TinyMrpConfig config = AddinContext.Config;
            if (config == null)
            {
                MessageBox.Show("Config is not initialized.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            UpdateConfigFromUi();
            _numberingClient = null;
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ApiResponse health = client.HealthCheck();
            if (!health.Ok)
            {
                ShowConnectionFailure(
                    "Server not reachable or Backend URL/proxy is wrong.",
                    health,
                    health.ResponseIsHtml
                        ? "The add-in reached a web page/login page instead of the JSON API."
                        : null);
                return;
            }

            ApiResponse response = client.AuthCheck();
            if (!response.Ok)
            {
                if (ResponseHasErrorCode(response, "token_required"))
                {
                    ShowConnectionFailure("Server reachable, but Auth token is missing.", response, null);
                }
                else if (ResponseHasErrorCode(response, "invalid_token") || ResponseHasErrorCode(response, "unauthorized"))
                {
                    ShowConnectionFailure(
                        "Server reachable, but the Auth token is invalid. Generate a new TinyMRP API token and paste the raw token into the add-in. Existing tokens may have been invalidated if the instance secret changed.",
                        response,
                        null);
                }
                else
                {
                    ShowConnectionFailure("Connection failed.", response, null);
                }
                return;
            }

            Dictionary<string, object> userDict = NumberingJson.GetDict(response.Data, "user");
            string email = userDict != null ? NumberingJson.GetString(userDict, "email") : string.Empty;
            MessageBox.Show("Connection OK" + (string.IsNullOrWhiteSpace(email) ? "" : " (" + email + ")") + ".",
                "TinyMRP", MessageBoxButtons.OK, MessageBoxIcon.Information);
            SetNumberingStatus("Connection OK.", Color.DarkGreen);
        }

        private void OnQuickDiagnostics(object sender, EventArgs e)
        {
            UpdateConfigFromUi();
            _numberingClient = null;
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            var details = new List<string>();
            TinyMrpConfig config = AddinContext.Config;
            details.Add("Backend URL: " + (config != null ? config.BackendUrl : ""));
            details.Add("Config path: " + (config != null ? config.ConfigPath : ""));
            details.Add(string.Empty);

            ApiResponse health = client.HealthCheck();
            AddDiagnosticResult(details, "Health check", health, health.Ok ? "OK" : "Failed");

            ApiResponse auth = null;
            if (health.Ok)
            {
                auth = client.AuthCheck();
                AddDiagnosticResult(details, "Auth check", auth, auth.Ok ? "OK" : "Failed");
            }
            else
            {
                details.Add("Auth check: Skipped because the health check failed.");
            }

            List<NumberingSchemeDefinition> schemes = new List<NumberingSchemeDefinition>();
            ApiResponse schemesResp = null;
            if (auth != null && auth.Ok)
            {
                schemesResp = client.ListSchemes(out schemes);
                AddDiagnosticResult(details, "Schemes load", schemesResp, schemesResp.Ok ? "OK (" + schemes.Count + " loaded)" : "Failed");
            }
            else
            {
                details.Add("Schemes load: Skipped because the auth check failed.");
            }

            UserSettingsDefinition settings = null;
            ApiResponse settingsResp = null;
            if (auth != null && auth.Ok)
            {
                settingsResp = client.GetUserSettings(out settings);
                AddDiagnosticResult(details, "Settings load", settingsResp, settingsResp.Ok ? "OK" : "Failed");
            }
            else
            {
                details.Add("Settings load: Skipped because the auth check failed.");
            }

            string schemeId = GetSchemeIdFromCombo(_quickSchemeCombo);
            if (settings != null && string.IsNullOrWhiteSpace(schemeId))
            {
                schemeId = settings.DefaultSchemeId;
            }

            if (string.IsNullOrWhiteSpace(schemeId))
            {
                details.Add("Preview test: Skipped because no scheme is selected.");
            }
            else if (auth == null || !auth.Ok)
            {
                details.Add("Preview test: Skipped because the auth check failed.");
            }
            else
            {
                var context = BuildContextFromQuickStart();
                ApiResponse preview = client.Preview(schemeId, context, BuildSequenceOverrideValues(GetQuickSchemeSelection()));
                AddDiagnosticResult(details, "Preview test", preview, preview.Ok ? "OK" : "Failed");
            }

            string detailText = string.Join(System.Environment.NewLine, details.ToArray());
            AddinLogger.Write("Diagnostics\n" + detailText);
            ShowMessageWithDetails("Diagnostics", "Diagnostics completed.", detailText);
        }

        private void OnQuickRefreshSchemes(object sender, EventArgs e)
        {
            UpdateConfigFromUi();
            _numberingClient = null;
            OnRefreshSchemes(sender, e);
        }

        private void OnQuickApplyDefaults(object sender, EventArgs e)
        {
            UpdateConfigFromUi();
            _numberingClient = null;
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ApiResponse response = client.GetUserSettings(out UserSettingsDefinition settings);
            if (!response.Ok)
            {
                ShowApiError("Failed to load settings.", response);
                return;
            }

            ApplyUserSettings(settings);
            MessageBox.Show("Server defaults loaded.", "TinyMRP",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        private void OnQuickSaveSettings(object sender, EventArgs e)
        {
            TinyMrpConfig config = AddinContext.Config;
            if (config == null)
            {
                MessageBox.Show("Config is not initialized.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            UpdateConfigFromUi();
            try
            {
                config.Save();
                _numberingClient = null;
                if (_configPathLabel != null)
                {
                    _configPathLabel.Text = "Config: " + config.ConfigPath;
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to save config: " + ex.Message, "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            MessageBox.Show("Settings saved.", "TinyMRP",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        private void OnAdvancedSaveSettings(object sender, EventArgs e)
        {
            UserSettingsDefinition settings = BuildUserSettingsFromAdvanced();
            if (settings == null)
            {
                return;
            }

            ApplyUserSettings(settings);
            _numberingClient = null;
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ApiResponse response = client.SaveUserSettings(settings);
            if (!response.Ok)
            {
                ShowApiError("Failed to save settings.", response);
                return;
            }

            MessageBox.Show("Server settings saved.", "TinyMRP",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        private void OnQuickPreview(object sender, EventArgs e)
        {
            string schemeId = GetSchemeIdFromCombo(_quickSchemeCombo);
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                MessageBox.Show("Select a numbering scheme.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ApiResponse response = client.Preview(schemeId, BuildContextFromQuickStart(), BuildSequenceOverrideValues(GetQuickSchemeSelection()));
            if (!response.Ok)
            {
                ShowApiError("Preview failed.", response);
                return;
            }

            ApplySequenceOverrideStateFromResponse(GetQuickSchemeSelection(), response, false);
            string partNumber = NumberingJson.GetString(response.Data, "candidate_part_number") ?? string.Empty;
            string revision = NumberingJson.GetString(response.Data, "candidate_revision") ?? string.Empty;
            string display = NumberingJson.GetString(response.Data, "display_code_candidate") ?? string.Empty;
            if (_quickPreviewLabel != null)
            {
                _quickPreviewLabel.Text = string.Format("Preview: {0} {1} {2}",
                    partNumber,
                    string.IsNullOrWhiteSpace(revision) ? "" : "Rev " + revision,
                    string.IsNullOrWhiteSpace(display) ? "" : "(" + display + ")");
            }
        }

        private void OnQuickGoToNumbering(object sender, EventArgs e)
        {
            if (_tabs != null && _tabs.TabPages.Count > 2)
            {
                _tabs.SelectedIndex = 2;
            }
        }


        private void OnNumberingPresetSelected(object sender, EventArgs e)
        {
            NumberingSchemeDefinition scheme = _numberingPresetCombo != null
                ? _numberingPresetCombo.SelectedItem as NumberingSchemeDefinition
                : null;
            UpdateQuickContextVisibility(scheme);
            if (scheme != null)
            {
                SyncSchemeSelection(_numberingPresetCombo, _quickSchemeCombo);
                SyncSchemeSelection(_numberingPresetCombo, _advancedSchemeCombo);
            }
            MaybeAutoAssignNumbering(false);
        }

        private void OnNumberingPreview(object sender, EventArgs e)
        {
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string schemeId = GetSchemeIdFromCombo(_numberingPresetCombo);
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                schemeId = GetDefaultSchemeId();
            }
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                SetNumberingStatus("Select a numbering scheme first.", Color.Maroon);
                return;
            }

            ApiResponse response = client.Preview(schemeId, BuildContextFromNumberingQuick(), BuildSequenceOverrideValues(GetQuickSchemeSelection()));
            if (!response.Ok)
            {
                ShowApiError("Preview failed.", response);
                SetNumberingStatus("Preview failed.", Color.Maroon);
                return;
            }

            ApplySequenceOverrideStateFromResponse(GetQuickSchemeSelection(), response, false);
            string partNumber = NumberingJson.GetString(response.Data, "candidate_part_number");
            string revision = NumberingJson.GetString(response.Data, "candidate_revision");
            string display = NumberingJson.GetString(response.Data, "display_code_candidate");
            if (string.IsNullOrWhiteSpace(display))
            {
                display = BuildDisplayCode(partNumber, revision);
            }
            UpdateQuickPreviewFields(partNumber, revision, display);
            SetNumberingStatus("Preview ready.", Color.DarkGreen);
        }

        private void OnNumberingAllocate(object sender, EventArgs e)
        {
            RunAllocateWorkflow(false);
        }

        private void OnNumberingAllocateRename(object sender, EventArgs e)
        {
            RunAllocateWorkflow(true);
        }

        private void OnNumberingAllocateSave(object sender, EventArgs e)
        {
            ISldWorks app = AddinContext.SldWorks;
            if (app == null)
            {
                MessageBox.Show("SolidWorks is not available.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ActiveModelInfo info;
            string error;
            if (!SolidWorksDocumentHelper.TryGetActiveModel(app, out info, out error))
            {
                MessageBox.Show(error, "TinyMRP", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            if (!string.IsNullOrWhiteSpace(info.Model.GetPathName()))
            {
                RunAllocateWorkflow(true);
                return;
            }

            RunAllocateAndSaveWorkflow(info);
        }

        private void RunAllocateWorkflow(bool forceRename)
        {
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string schemeId = GetSchemeIdFromCombo(_numberingPresetCombo);
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                schemeId = GetDefaultSchemeId();
            }
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                SetNumberingStatus("Select a numbering scheme first.", Color.Maroon);
                return;
            }

            ISldWorks app = AddinContext.SldWorks;
            if (app == null)
            {
                MessageBox.Show("SolidWorks is not available.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ActiveModelInfo info;
            string error;
            if (!SolidWorksDocumentHelper.TryGetActiveModel(app, out info, out error))
            {
                MessageBox.Show(error, "TinyMRP", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ApiResponse response = client.Allocate(
                schemeId,
                BuildContextFromNumberingQuick(),
                "new_part",
                string.Empty,
                true,
                BuildCadRef(info),
                BuildSequenceOverrideValues(GetQuickSchemeSelection()));

            if (!response.Ok)
            {
                ShowApiError("Allocation failed.", response);
                SetNumberingStatus("Allocation failed.", Color.Maroon);
                return;
            }

            ApplySequenceOverrideStateFromResponse(GetQuickSchemeSelection(), response, true);
            string partNumber = NumberingJson.GetString(response.Data, "part_number");
            string revision = NumberingJson.GetString(response.Data, "revision");
            if (string.IsNullOrWhiteSpace(partNumber))
            {
                SetNumberingStatus("Allocation returned no part number.", Color.Maroon);
                return;
            }

            revision = ResolveRevisionForApply(info, revision);
            string display = NumberingJson.GetString(response.Data, "display_code");
            if (string.IsNullOrWhiteSpace(display) || string.IsNullOrWhiteSpace(revision))
            {
                display = BuildDisplayCode(partNumber, revision);
            }

            UpdateQuickPreviewFields(partNumber, revision, display);

            if (!ApplyNumberingToModelQuick(info, partNumber, revision, display, schemeId))
            {
                SetNumberingStatus("Failed to apply properties.", Color.Maroon);
                return;
            }

            SetNumberingStatus("Allocated and applied.", Color.DarkGreen);
            TryRenameAfterAllocation(info, partNumber, revision, forceRename);
        }

        private void RunAllocateAndSaveWorkflow(ActiveModelInfo info)
        {
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string schemeId = GetSchemeIdFromCombo(_numberingPresetCombo);
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                schemeId = GetDefaultSchemeId();
            }
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                SetNumberingStatus("Select a numbering scheme first.", Color.Maroon);
                return;
            }

            string targetFolder;
            if (!TryPromptForAllocateSaveFolder(out targetFolder))
            {
                SetNumberingStatus("Allocate and Save cancelled.", Color.DarkOrange);
                return;
            }

            ApiResponse response = client.Allocate(
                schemeId,
                BuildContextFromNumberingQuick(),
                "new_part",
                string.Empty,
                true,
                BuildCadRef(info),
                BuildSequenceOverrideValues(GetQuickSchemeSelection()));

            if (!response.Ok)
            {
                ShowApiError("Allocation failed.", response);
                SetNumberingStatus("Allocation failed.", Color.Maroon);
                return;
            }

            ApplySequenceOverrideStateFromResponse(GetQuickSchemeSelection(), response, true);
            string partNumber = NumberingJson.GetString(response.Data, "part_number");
            string revision = NumberingJson.GetString(response.Data, "revision");
            if (string.IsNullOrWhiteSpace(partNumber))
            {
                SetNumberingStatus("Allocation returned no part number.", Color.Maroon);
                return;
            }

            revision = ResolveRevisionForApply(info, revision);
            string display = NumberingJson.GetString(response.Data, "display_code");
            if (string.IsNullOrWhiteSpace(display) || string.IsNullOrWhiteSpace(revision))
            {
                display = BuildDisplayCode(partNumber, revision);
            }

            UpdateQuickPreviewFields(partNumber, revision, display);

            if (!ApplyNumberingToModelQuick(info, partNumber, revision, display, schemeId))
            {
                SetNumberingStatus("Failed to apply properties.", Color.Maroon);
                return;
            }

            string extension;
            if (!TryGetSolidWorksExtension(info.Model, out extension))
            {
                SetNumberingStatus("Unsupported SolidWorks document type.", Color.Maroon);
                MessageBox.Show("Only part, assembly, and drawing documents are supported for Allocate and Save.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string targetPath;
            string pathMessage;
            if (!PartNumberRenameHelper.TryBuildUnsavedTargetPath(targetFolder, partNumber, extension, File.Exists, out targetPath, out pathMessage))
            {
                AddinLogger.Write("Allocate and Save target rejected: " + pathMessage);
                SetNumberingStatus(pathMessage, Color.Maroon);
                MessageBox.Show(pathMessage, "TinyMRP", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string saveMessage;
            bool hadWarnings;
            if (!TrySaveAllocatedModelToPath(info, targetPath, out saveMessage, out hadWarnings))
            {
                AddinLogger.Write("Allocate and Save failed: " + saveMessage);
                SetNumberingStatus("Allocated, but save failed.", Color.Maroon);
                ShowMessageWithDetails("Save failed", "Allocated, but Save As failed.", saveMessage);
                return;
            }

            string successMessage = hadWarnings
                ? "Allocated and saved with SolidWorks warnings."
                : "Allocated and saved.";
            AddinLogger.Write("Allocate and Save completed: " + targetPath);
            SetNumberingStatus(successMessage, Color.DarkGreen);
            ShowMessageWithDetails("Allocate and Save", successMessage, saveMessage);
        }

        private NumberingSchemeDefinition GetQuickSchemeSelection()
        {
            if (_numberingPresetCombo != null)
            {
                return _numberingPresetCombo.SelectedItem as NumberingSchemeDefinition;
            }
            if (_quickSchemeCombo != null)
            {
                return _quickSchemeCombo.SelectedItem as NumberingSchemeDefinition;
            }
            return null;
        }

        private List<int> BuildSequenceOverrideValues(NumberingSchemeDefinition scheme)
        {
            if (scheme == null || _numberingSeqOverrides == null || _numberingSeqOverrides.Count == 0)
            {
                return null;
            }

            var values = new List<int>();
            foreach (NumericUpDown upDown in _numberingSeqOverrides)
            {
                values.Add((int)upDown.Value);
            }
            return values;
        }

        private void UpdateQuickPreviewFields(string partNumber, string revision, string display)
        {
            if (_numberingPreviewPartText != null)
            {
                _numberingPreviewPartText.Text = partNumber ?? string.Empty;
            }
            if (_numberingPreviewRevisionText != null)
            {
                _numberingPreviewRevisionText.Text = revision ?? string.Empty;
            }
            if (_numberingPreviewDisplayText != null)
            {
                _numberingPreviewDisplayText.Text = display ?? string.Empty;
            }
        }

        private void SetNumberingStatus(string message, Color color)
        {
            if (_numberingStatusLabel == null)
            {
                return;
            }

            _numberingStatusLabel.Text = message ?? string.Empty;
            _numberingStatusLabel.ForeColor = color;
        }

        private bool ApplyNumberingToModelQuick(ActiveModelInfo info, string partNumber, string revision, string displayCode, string schemeId)
        {
            if (info == null || info.Model == null)
            {
                return false;
            }

            var configs = new List<string>();
            if (!string.IsNullOrWhiteSpace(info.ActiveConfiguration))
            {
                configs.Add(info.ActiveConfiguration);
            }

            string partProp = AddinContext.Config != null ? AddinContext.Config.PartNumberProperty : "PartNumber";
            string revProp = AddinContext.Config != null ? AddinContext.Config.RevisionProperty : "Revision";
            string displayProp = AddinContext.Config != null ? AddinContext.Config.DisplayCodeProperty : "DisplayCode";

            SolidWorksPropertyWriter.ApplyNumbering(
                info.Model,
                configs,
                true,
                partNumber,
                revision,
                displayCode,
                schemeId,
                partProp,
                revProp,
                displayProp);

            if (info.StartedFromDrawing)
            {
                ISldWorks app = AddinContext.SldWorks;
                if (app != null)
                {
                    app.ActivateDoc(info.StartTitle);
                }
            }

            return true;
        }

        private RenameOptions BuildRenameOptions()
        {
            var options = new RenameOptions
            {
                Mode = GetRenameMode(),
                AppendRevision = _renameAppendRevisionCheck != null && _renameAppendRevisionCheck.Checked,
                KeepBackup = _renameKeepBackupCheck == null || _renameKeepBackupCheck.Checked,
                RenameChildren = _renameChildrenCheck != null && _renameChildrenCheck.Checked
            };
            return options;
        }

        private RenameMode GetRenameMode()
        {
            string mode = _renameModeCombo != null && _renameModeCombo.SelectedItem is string text
                ? text
                : string.Empty;
            if (mode.StartsWith("Rename", StringComparison.OrdinalIgnoreCase))
            {
                return RenameMode.RenameIfNotReferenced;
            }
            return RenameMode.Safe;
        }

        private void TryRenameAfterAllocation(ActiveModelInfo info, string partNumber, string revision, bool forceRename)
        {
            bool autoRename = _renameAutoCheck != null && _renameAutoCheck.Checked;
            if (!forceRename && !autoRename)
            {
                return;
            }

            var options = BuildRenameOptions();
            var service = new SolidWorksRenameService();
            RenameResult result = service.TryRename(info.Model, partNumber, revision, options);
            AddinLogger.Write("Rename result: " + result.Message);

            if (!result.Ok)
            {
                SetNumberingStatus(result.Message, Color.Maroon);
                return;
            }

            if (options.RenameChildren)
            {
                AssemblyDoc assembly = info.Model as AssemblyDoc;
                if (assembly != null)
                {
                    RenameAssemblyChildren(assembly, options);
                }
            }

            if (info.StartedFromDrawing)
            {
                ISldWorks app = AddinContext.SldWorks;
                if (app != null)
                {
                    app.ActivateDoc(info.StartTitle);
                }
            }

            SetNumberingStatus(result.Message, Color.DarkGreen);
        }

        private bool TryPromptForAllocateSaveFolder(out string targetFolder)
        {
            targetFolder = string.Empty;
            string initialFolder = string.Empty;

            TinyMrpConfig config = AddinContext.Config;
            if (config != null && !string.IsNullOrWhiteSpace(config.DeliverablesFolder))
            {
                initialFolder = config.DeliverablesFolder;
            }
            if (string.IsNullOrWhiteSpace(initialFolder))
            {
                initialFolder = System.Environment.GetFolderPath(System.Environment.SpecialFolder.MyDocuments);
            }

            using (var dialog = new FolderBrowserDialog())
            {
                dialog.Description = "Choose where to save the allocated SolidWorks file.";
                dialog.ShowNewFolderButton = true;
                if (!string.IsNullOrWhiteSpace(initialFolder) && Directory.Exists(initialFolder))
                {
                    dialog.SelectedPath = initialFolder;
                }

                if (dialog.ShowDialog(this) != DialogResult.OK)
                {
                    return false;
                }

                targetFolder = dialog.SelectedPath ?? string.Empty;
                return !string.IsNullOrWhiteSpace(targetFolder);
            }
        }

        private bool TryGetSolidWorksExtension(ModelDoc2 model, out string extension)
        {
            extension = string.Empty;
            if (model == null)
            {
                return false;
            }

            switch (model.GetType())
            {
                case (int)swDocumentTypes_e.swDocPART:
                    extension = ".sldprt";
                    return true;
                case (int)swDocumentTypes_e.swDocASSEMBLY:
                    extension = ".sldasm";
                    return true;
                case (int)swDocumentTypes_e.swDocDRAWING:
                    extension = ".slddrw";
                    return true;
                default:
                    return false;
            }
        }

        private bool TrySaveAllocatedModelToPath(ActiveModelInfo info, string targetPath, out string message, out bool hadWarnings)
        {
            message = string.Empty;
            hadWarnings = false;

            if (info == null || info.Model == null)
            {
                message = "Active document not found.";
                return false;
            }

            int errors = 0;
            int warnings = 0;
            bool ok = info.Model.Extension.SaveAs(
                targetPath,
                (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                (int)swSaveAsOptions_e.swSaveAsOptions_Silent,
                null,
                ref errors,
                ref warnings);

            if (!ok)
            {
                message = "SolidWorks Save As failed. Errors=" + errors + " Warnings=" + warnings;
                return false;
            }

            hadWarnings = warnings != 0;
            message = "Saved to " + targetPath + System.Environment.NewLine +
                "Errors=" + errors + System.Environment.NewLine +
                "Warnings=" + warnings;
            return true;
        }

        private void MaybeAutoAssignNumbering(bool userTriggered)
        {
            if (_autoAssignGenericCheck == null || !_autoAssignGenericCheck.Checked)
            {
                return;
            }

            ISldWorks app = AddinContext.SldWorks;
            if (app == null)
            {
                return;
            }

            ActiveModelInfo info;
            string error;
            if (!SolidWorksDocumentHelper.TryGetActiveModel(app, out info, out error))
            {
                if (userTriggered)
                {
                    SetNumberingStatus(error, Color.Maroon);
                }
                return;
            }

            if (!ShouldAutoAssignForModel(info.Model))
            {
                return;
            }

            string key = GetModelKey(info.Model);
            if (_autoAssignedModels.Contains(key))
            {
                return;
            }

            string existing = TryReadPartNumberFromModel(info);
            if (!string.IsNullOrWhiteSpace(existing))
            {
                return;
            }

            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                SetNumberingStatus("Backend URL is not configured.", Color.Maroon);
                return;
            }

            string schemeId = GetSchemeIdFromCombo(_numberingPresetCombo);
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                schemeId = GetDefaultSchemeId();
            }
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                SetNumberingStatus("Select a numbering scheme first.", Color.Maroon);
                return;
            }

            ApiResponse response = client.Allocate(
                schemeId,
                BuildContextFromNumberingQuick(),
                "new_part",
                string.Empty,
                true,
                BuildCadRef(info),
                BuildSequenceOverrideValues(GetQuickSchemeSelection()));

            if (!response.Ok)
            {
                HandleApiError("Auto-assign failed.", response, false);
                return;
            }

            ApplySequenceOverrideStateFromResponse(GetQuickSchemeSelection(), response, true);
            string partNumber = NumberingJson.GetString(response.Data, "part_number");
            string revision = NumberingJson.GetString(response.Data, "revision");
            if (string.IsNullOrWhiteSpace(partNumber))
            {
                SetNumberingStatus("Auto-assign returned no part number.", Color.Maroon);
                return;
            }

            revision = ResolveRevisionForApply(info, revision);
            string display = NumberingJson.GetString(response.Data, "display_code");
            if (string.IsNullOrWhiteSpace(display) || string.IsNullOrWhiteSpace(revision))
            {
                display = BuildDisplayCode(partNumber, revision);
            }

            UpdateQuickPreviewFields(partNumber, revision, display);

            if (!ApplyNumberingToModelQuick(info, partNumber, revision, display, schemeId))
            {
                SetNumberingStatus("Auto-assign failed to apply properties.", Color.Maroon);
                return;
            }

            _autoAssignedModels.Add(key);
            SetNumberingStatus("Auto-assigned part number.", Color.DarkGreen);
            TryRenameAfterAllocation(info, partNumber, revision, false);
        }

        private bool ShouldAutoAssignForModel(ModelDoc2 model)
        {
            if (model == null)
            {
                return false;
            }

            bool allowAny = _autoAssignAnyNameCheck != null && _autoAssignAnyNameCheck.Checked;
            if (allowAny)
            {
                return true;
            }

            return IsGenericSolidWorksName(model.GetTitle());
        }

        private static string GetModelKey(ModelDoc2 model)
        {
            if (model == null)
            {
                return string.Empty;
            }

            string path = model.GetPathName();
            if (!string.IsNullOrWhiteSpace(path))
            {
                return path;
            }
            return model.GetTitle() ?? string.Empty;
        }

        private static bool IsGenericSolidWorksName(string title)
        {
            if (string.IsNullOrWhiteSpace(title))
            {
                return false;
            }

            string name = Path.GetFileNameWithoutExtension(title).Trim();
            if (string.IsNullOrWhiteSpace(name))
            {
                return false;
            }

            return HasNumericSuffix(name, "Part") ||
                   HasNumericSuffix(name, "Assembly") ||
                   HasNumericSuffix(name, "Drawing");
        }

        private static bool HasNumericSuffix(string name, string prefix)
        {
            if (!name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            string suffix = name.Substring(prefix.Length);
            if (suffix.Length == 0)
            {
                return false;
            }

            foreach (char ch in suffix)
            {
                if (!char.IsDigit(ch))
                {
                    return false;
                }
            }

            return true;
        }

        private string TryReadPartNumberFromModel(ActiveModelInfo info)
        {
            if (info == null || info.Model == null)
            {
                return string.Empty;
            }

            string propName = AddinContext.Config != null ? AddinContext.Config.PartNumberProperty : "PartNumber";
            if (string.IsNullOrWhiteSpace(propName))
            {
                propName = "PartNumber";
            }

            string value = GetCustomProperty(info.Model, info.ActiveConfiguration, propName);
            if (string.IsNullOrWhiteSpace(value))
            {
                value = GetCustomProperty(info.Model, string.Empty, propName);
            }

            if (info.StartedFromDrawing)
            {
                ISldWorks app = AddinContext.SldWorks;
                if (app != null)
                {
                    app.ActivateDoc(info.StartTitle);
                }
            }

            return value ?? string.Empty;
        }

        private void RenameAssemblyChildren(AssemblyDoc assembly, RenameOptions options)
        {
            if (assembly == null)
            {
                return;
            }

            object componentsObj = null;
            try
            {
                componentsObj = assembly.GetComponents(false);
            }
            catch
            {
                componentsObj = null;
            }

            if (ComInteropUtil.GetComLength(componentsObj) == 0)
            {
                return;
            }

            string partProp = AddinContext.Config != null ? AddinContext.Config.PartNumberProperty : "PartNumber";
            string revProp = AddinContext.Config != null ? AddinContext.Config.RevisionProperty : "Revision";
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var service = new SolidWorksRenameService();

            foreach (object item in ComInteropUtil.EnumerateCom(componentsObj))
            {
                Component2 component = item as Component2;
                if (component == null || component.IsSuppressed())
                {
                    continue;
                }

                string path = component.GetPathName();
                if (string.IsNullOrWhiteSpace(path) || !seen.Add(path))
                {
                    continue;
                }

                ModelDoc2 model = component.GetModelDoc2() as ModelDoc2;
                if (model == null)
                {
                    continue;
                }

                string configName = component.ReferencedConfiguration;
                string pn = GetCustomProperty(model, configName, partProp);
                if (string.IsNullOrWhiteSpace(pn))
                {
                    continue;
                }
                string rev = GetCustomProperty(model, configName, revProp);

                RenameResult childResult = service.TryRename(model, pn, rev, options);
                AddinLogger.Write("Rename child " + path + ": " + childResult.Message);
            }
        }

        private void OnRenameDryRun(object sender, EventArgs e)
        {
            ISldWorks app = AddinContext.SldWorks;
            if (app == null)
            {
                MessageBox.Show("SolidWorks is not available.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ActiveModelInfo info;
            string error;
            if (!SolidWorksDocumentHelper.TryGetActiveModel(app, out info, out error))
            {
                MessageBox.Show(error, "TinyMRP", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string partNumber = _numberingPreviewPartText != null ? _numberingPreviewPartText.Text.Trim() : string.Empty;
            string revision = _numberingPreviewRevisionText != null ? _numberingPreviewRevisionText.Text.Trim() : string.Empty;
            if (string.IsNullOrWhiteSpace(partNumber))
            {
                partNumber = GetCustomProperty(info.Model, info.ActiveConfiguration, AddinContext.Config != null ? AddinContext.Config.PartNumberProperty : "PartNumber");
            }
            if (string.IsNullOrWhiteSpace(revision))
            {
                revision = GetCustomProperty(info.Model, info.ActiveConfiguration, AddinContext.Config != null ? AddinContext.Config.RevisionProperty : "Revision");
            }

            var options = BuildRenameOptions();
            var service = new SolidWorksRenameService();
            RenameResult preview = service.PreviewRename(info.Model, partNumber, revision, options);
            if (!preview.Ok)
            {
                MessageBox.Show(preview.Message, "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string details = "Current: " + preview.CurrentPath + System.Environment.NewLine +
                            "Proposed: " + preview.TargetPath;
            MessageBox.Show(details, "Rename dry run", MessageBoxButtons.OK, MessageBoxIcon.Information);
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

        // Numbering helpers

        private NumberingApiClient GetNumberingClient()
        {
            if (_numberingClient != null)
            {
                return _numberingClient;
            }

            TinyMrpConfig config = AddinContext.Config;
            if (config == null)
            {
                return null;
            }

            _numberingClient = new NumberingApiClient(config);
            return _numberingClient;
        }

        private void InitializeNumberingDefaults()
        {
            if (_currentScheme == null)
            {
                _currentScheme = NumberingSchemeCatalog.CreateBasicScheme();
            }

            if (_presetCombo != null && _presetCombo.SelectedIndex < 0)
            {
                _presetCombo.SelectedIndex = 0;
            }

            if (_separatorText != null && string.IsNullOrWhiteSpace(_separatorText.Text))
            {
                _separatorText.Text = "-";
            }

            if (_scopeModeCombo != null && _scopeModeCombo.SelectedIndex < 0)
            {
                _scopeModeCombo.SelectedIndex = 0;
            }

            if (_seqBaseCombo != null && _seqBaseCombo.SelectedIndex < 0)
            {
                _seqBaseCombo.SelectedIndex = 0;
            }

            if (_seqResetCombo != null && _seqResetCombo.SelectedIndex < 0)
            {
                _seqResetCombo.SelectedIndex = 0;
            }

            if (_revPolicyCombo != null && _revPolicyCombo.SelectedIndex < 0)
            {
                _revPolicyCombo.SelectedIndex = 0;
            }

            if (_allowedCharsetText != null && string.IsNullOrWhiteSpace(_allowedCharsetText.Text))
            {
                _allowedCharsetText.Text = "A-Z0-9-";
            }

            if (_requireSeqCheck != null && !_requireSeqCheck.Checked)
            {
                _requireSeqCheck.Checked = true;
            }

            if (_segmentKindCombo != null && _segmentKindCombo.SelectedIndex < 0)
            {
                _segmentKindCombo.SelectedIndex = 0;
            }


            if (_segmentSeqBaseCombo != null && _segmentSeqBaseCombo.SelectedIndex < 0)
            {
                _segmentSeqBaseCombo.SelectedIndex = 0;
            }

            if (_segmentDateFmtCombo != null && _segmentDateFmtCombo.SelectedIndex < 0)
            {
                _segmentDateFmtCombo.SelectedIndex = 0;
            }

            if (_revisionActionCombo != null && _revisionActionCombo.SelectedIndex < 0)
            {
                _revisionActionCombo.SelectedIndex = 0;
            }

            if (_applyScopeCombo != null && _applyScopeCombo.SelectedIndex < 0)
            {
                _applyScopeCombo.SelectedIndex = 0;
            }

            if (_quickApplyModeCombo != null && _quickApplyModeCombo.SelectedIndex < 0)
            {
                _quickApplyModeCombo.SelectedIndex = 0;
            }

            if (_advancedApplyModeCombo != null && _advancedApplyModeCombo.SelectedIndex < 0)
            {
                _advancedApplyModeCombo.SelectedIndex = 0;
            }

            if (_renameModeCombo != null && _renameModeCombo.SelectedIndex < 0)
            {
                _renameModeCombo.SelectedIndex = 0;
            }

            if (_applyDocPropsCheck != null && !_applyDocPropsCheck.Checked)
            {
                _applyDocPropsCheck.Checked = true;
            }

            if (_createPartCheck != null && !_createPartCheck.Checked)
            {
                _createPartCheck.Checked = true;
            }

            UpdateSegmentEditorState();
            ApplyNumberingDefaults(AddinContext.Config);

            TinyMrpConfig config = AddinContext.Config;
            if (config != null &&
                (!string.IsNullOrWhiteSpace(config.BackendUrl) || !string.IsNullOrWhiteSpace(config.WebLink)))
            {
                RefreshSchemes(false);
            }
        }

        private void ApplyNumberingDefaults(TinyMrpConfig config)
        {
            if (config == null)
            {
                return;
            }

            if (_schemeCombo != null && !string.IsNullOrWhiteSpace(config.NumberingSchemeId))
            {
                _schemeCombo.Tag = config.NumberingSchemeId;
                SelectSchemeOrFallback(_schemeCombo, config.NumberingSchemeId, false);
            }
            if (_quickSchemeCombo != null && !string.IsNullOrWhiteSpace(config.NumberingSchemeId))
            {
                _quickSchemeCombo.Tag = config.NumberingSchemeId;
                SelectSchemeOrFallback(_quickSchemeCombo, config.NumberingSchemeId, true);
            }
            if (_numberingPresetCombo != null && !string.IsNullOrWhiteSpace(config.NumberingSchemeId))
            {
                _numberingPresetCombo.Tag = config.NumberingSchemeId;
                SelectSchemeOrFallback(_numberingPresetCombo, config.NumberingSchemeId, true);
            }
            if (_advancedSchemeCombo != null && !string.IsNullOrWhiteSpace(config.NumberingSchemeId))
            {
                _advancedSchemeCombo.Tag = config.NumberingSchemeId;
                SelectSchemeOrFallback(_advancedSchemeCombo, config.NumberingSchemeId, false);
            }

            if (_quickPartNumberPropText != null)
            {
                _quickPartNumberPropText.Text = config.PartNumberProperty ?? "PartNumber";
            }
            if (_quickRevisionPropText != null)
            {
                _quickRevisionPropText.Text = config.RevisionProperty ?? "Revision";
            }
            if (_quickDisplayCodePropText != null)
            {
                _quickDisplayCodePropText.Text = config.DisplayCodeProperty ?? "DisplayCode";
            }
            if (_partNumberPropText != null)
            {
                _partNumberPropText.Text = config.PartNumberProperty ?? "PartNumber";
            }
            if (_revisionPropText != null)
            {
                _revisionPropText.Text = config.RevisionProperty ?? "Revision";
            }
            if (_displayCodePropText != null)
            {
                _displayCodePropText.Text = config.DisplayCodeProperty ?? "DisplayCode";
            }
            if (_numberingPartNumberPropText != null)
            {
                _numberingPartNumberPropText.Text = config.PartNumberProperty ?? "PartNumber";
            }
            if (_numberingRevisionPropText != null)
            {
                _numberingRevisionPropText.Text = config.RevisionProperty ?? "Revision";
            }
            if (_numberingDisplayCodePropText != null)
            {
                _numberingDisplayCodePropText.Text = config.DisplayCodeProperty ?? "DisplayCode";
            }

            SelectApplyModeCombo(_quickApplyModeCombo, config.NumberingApplyMode);
            SelectApplyModeCombo(_advancedApplyModeCombo, config.NumberingApplyMode);
            SelectApplyModeCombo(_applyScopeCombo, config.NumberingApplyMode);

            if (_autoAssignGenericCheck != null)
            {
                _autoAssignGenericCheck.Checked = config.AutoAssignGenericNames;
            }
            if (_autoAssignAnyNameCheck != null)
            {
                _autoAssignAnyNameCheck.Checked = config.AutoAssignAnyNames;
            }

            if (_advancedContextJsonText != null)
            {
                _advancedContextJsonText.Text = ContextToJson(new Dictionary<string, string>());
            }

            if (_existingPartNumberText != null && string.IsNullOrWhiteSpace(_existingPartNumberText.Text))
            {
                string partNumber = TryReadPartNumberFromActiveDoc();
                if (!string.IsNullOrWhiteSpace(partNumber))
                {
                    _existingPartNumberText.Text = partNumber;
                }
            }

            UpdateQuickContextVisibility(_numberingPresetCombo != null
                ? _numberingPresetCombo.SelectedItem as NumberingSchemeDefinition
                : (_quickSchemeCombo != null ? _quickSchemeCombo.SelectedItem as NumberingSchemeDefinition : null));
            if (_renameModeCombo != null && _renameModeCombo.SelectedIndex < 0)
            {
                _renameModeCombo.SelectedIndex = 0;
            }
        }

        private void OnSaveNumberingDefaults(object sender, EventArgs e)
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
                MessageBox.Show("Defaults saved.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show("Failed to save defaults: " + ex.Message, "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void OnRefreshSchemes(object sender, EventArgs e)
        {
            RefreshSchemes(true);
        }

        private void RefreshSchemes(bool showDialogs)
        {
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                SetNumberingStatus("Backend URL is not configured.", Color.Maroon);
                if (showDialogs)
                {
                    MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                }
                return;
            }

            TinyMrpConfig config = AddinContext.Config;
            if (config != null && string.IsNullOrWhiteSpace(config.AuthToken))
            {
                SetNumberingStatus("Auth token is missing. Load schemes in Configuration.", Color.Maroon);
                if (showDialogs)
                {
                    MessageBox.Show("Auth token is missing. Set it in Configuration to load schemes.", "TinyMRP",
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                }
                return;
            }

            ApiResponse response = client.ListSchemes(out List<NumberingSchemeDefinition> schemes);
            if (!response.Ok)
            {
                HandleApiError("Failed to load schemes.", response, showDialogs);
                return;
            }

            _loadedSchemes.Clear();
            _sequenceOverrideCache.Clear();
            _loadedSchemes.AddRange(schemes);
            PopulateSchemeCombo(_schemeCombo, _loadedSchemes, true);
            PopulateSchemeCombo(_advancedSchemeCombo, _loadedSchemes, false);
            PopulateQuickSchemeCombo();
            List<NumberingSchemeDefinition> selectableSchemes = GetQuickSchemes();
            SetNumberingStatus(
                selectableSchemes.Count > 0 ? "Schemes loaded." : "No active numbering schemes are available.",
                selectableSchemes.Count > 0 ? Color.DarkGreen : Color.Maroon);
            MaybeAutoAssignNumbering(false);
        }

        private void PopulateSchemeCombo(ComboBox combo, List<NumberingSchemeDefinition> schemes, bool includeNew)
        {
            if (combo == null)
            {
                return;
            }

            combo.Items.Clear();
            if (includeNew)
            {
                combo.Items.Add(NumberingSchemeCatalog.CreateBasicScheme(NumberingSchemeCatalog.NewSchemePlaceholderName));
            }

            if (schemes != null)
            {
                foreach (NumberingSchemeDefinition scheme in schemes)
                {
                    combo.Items.Add(scheme);
                }
            }

            string preferredId = combo.Tag as string;
            if (string.IsNullOrWhiteSpace(preferredId))
            {
                preferredId = AddinContext.Config != null ? AddinContext.Config.NumberingSchemeId : string.Empty;
            }

            if (!string.IsNullOrWhiteSpace(preferredId))
            {
                SelectSchemeOrFallback(combo, preferredId, false);
            }
            else if (combo.Items.Count > 0)
            {
                combo.SelectedIndex = 0;
                combo.Tag = GetSchemeIdFromCombo(combo);
            }
        }

        private void PopulateQuickSchemeCombo()
        {
            if (_quickSchemeCombo == null && _numberingPresetCombo == null)
            {
                return;
            }

            List<NumberingSchemeDefinition> quickSchemes = GetQuickSchemes();
            PopulatePresetCombo(_quickSchemeCombo, quickSchemes);
            PopulatePresetCombo(_numberingPresetCombo, quickSchemes);

            UpdateQuickContextVisibility(_numberingPresetCombo != null ? _numberingPresetCombo.SelectedItem as NumberingSchemeDefinition : _quickSchemeCombo.SelectedItem as NumberingSchemeDefinition);
        }

        private void PopulatePresetCombo(ComboBox combo, List<NumberingSchemeDefinition> quickSchemes)
        {
            if (combo == null)
            {
                return;
            }

            combo.Items.Clear();
            foreach (NumberingSchemeDefinition scheme in quickSchemes)
            {
                combo.Items.Add(scheme);
            }

            string preferredId = combo.Tag as string;
            if (string.IsNullOrWhiteSpace(preferredId))
            {
                preferredId = AddinContext.Config != null ? AddinContext.Config.NumberingSchemeId : string.Empty;
            }

            SelectSchemeOrFallback(combo, preferredId, true);
        }

        private void SelectSchemeOrFallback(ComboBox combo, string preferredId, bool preferRecommended)
        {
            if (combo == null)
            {
                return;
            }

            if (combo.Items.Count == 0)
            {
                combo.SelectedIndex = -1;
                combo.Tag = string.IsNullOrWhiteSpace(preferredId) ? string.Empty : preferredId.Trim();
                return;
            }

            if (!string.IsNullOrWhiteSpace(preferredId))
            {
                SelectComboItem(combo, preferredId);
                if (combo.SelectedIndex >= 0)
                {
                    combo.Tag = GetSchemeIdFromCombo(combo);
                    return;
                }
            }

            if (preferRecommended)
            {
                for (int i = 0; i < combo.Items.Count; i++)
                {
                    NumberingSchemeDefinition scheme = combo.Items[i] as NumberingSchemeDefinition;
                    if (scheme != null && scheme.IsRecommended)
                    {
                        combo.SelectedIndex = i;
                        combo.Tag = scheme.Id ?? string.Empty;
                        return;
                    }
                }
            }

            if (combo.Items.Count > 0)
            {
                combo.SelectedIndex = 0;
                combo.Tag = GetSchemeIdFromCombo(combo);
                return;
            }

            combo.SelectedIndex = -1;
            combo.Tag = string.Empty;
        }

        private List<NumberingSchemeDefinition> GetQuickSchemes()
        {
            return NumberingSchemeCatalog.GetSelectableSchemes(_loadedSchemes);
        }

        private void OnSchemeSelected(object sender, EventArgs e)
        {
            NumberingSchemeDefinition scheme = _schemeCombo != null
                ? _schemeCombo.SelectedItem as NumberingSchemeDefinition
                : null;

            if (scheme == null)
            {
                return;
            }

            _currentScheme = scheme;
            ApplySchemeToUi(scheme);
        }

        private void OnApplyPreset(object sender, EventArgs e)
        {
            if (_currentScheme == null)
            {
                _currentScheme = NumberingSchemeCatalog.CreateBasicScheme();
            }

            int presetIndex = _presetCombo != null ? _presetCombo.SelectedIndex : -1;
            if (presetIndex < 0)
            {
                presetIndex = 0;
            }

            if (presetIndex >= 0)
            {
                NumberingSchemeCatalog.ApplyBasicTemplate(_currentScheme, "PART", 6, true);
            }
            ApplySchemeToUi(_currentScheme);
        }

        private void OnSegmentSelected(object sender, EventArgs e)
        {
            var segment = _segmentsList != null ? _segmentsList.SelectedItem as NumberingSegmentDefinition : null;
            if (segment == null)
            {
                return;
            }

            SelectComboItem(_segmentKindCombo, segment.Kind);
            _segmentLiteralText.Text = segment.Value ?? string.Empty;
            _segmentSeqPaddingUpDown.Value = segment.Padding.HasValue ? segment.Padding.Value : _segmentSeqPaddingUpDown.Value;
            SelectComboItem(_segmentSeqBaseCombo, segment.Base.HasValue ? segment.Base.Value.ToString() : string.Empty);
            if (_segmentSeqStartUpDown != null)
            {
                int segmentStart = segment.StartAt.HasValue && segment.StartAt.Value > 0
                    ? segment.StartAt.Value
                    : (_seqStartUpDown != null ? (int)_seqStartUpDown.Value : 1);
                _segmentSeqStartUpDown.Value = segmentStart;
            }
            if (_segmentSeqAutoCheck != null)
            {
                _segmentSeqAutoCheck.Checked = segment.AutoCounter;
            }
            SelectComboItem(_segmentDateFmtCombo, segment.Fmt);
            UpdateSegmentEditorState();
        }

        private void OnMoveSegmentUp(object sender, EventArgs e)
        {
            if (_segmentsList == null || _currentScheme == null)
            {
                return;
            }

            int index = _segmentsList.SelectedIndex;
            if (index <= 0 || index >= _currentScheme.PatternSegments.Count)
            {
                return;
            }

            NumberingSegmentDefinition segment = _currentScheme.PatternSegments[index];
            _currentScheme.PatternSegments.RemoveAt(index);
            _currentScheme.PatternSegments.Insert(index - 1, segment);
            UpdateSegmentsList();
            _segmentsList.SelectedIndex = index - 1;
        }

        private void OnMoveSegmentDown(object sender, EventArgs e)
        {
            if (_segmentsList == null || _currentScheme == null)
            {
                return;
            }

            int index = _segmentsList.SelectedIndex;
            if (index < 0 || index >= _currentScheme.PatternSegments.Count - 1)
            {
                return;
            }

            NumberingSegmentDefinition segment = _currentScheme.PatternSegments[index];
            _currentScheme.PatternSegments.RemoveAt(index);
            _currentScheme.PatternSegments.Insert(index + 1, segment);
            UpdateSegmentsList();
            _segmentsList.SelectedIndex = index + 1;
        }

        private void OnRemoveSegment(object sender, EventArgs e)
        {
            if (_segmentsList == null || _currentScheme == null)
            {
                return;
            }

            int index = _segmentsList.SelectedIndex;
            if (index < 0 || index >= _currentScheme.PatternSegments.Count)
            {
                return;
            }

            _currentScheme.PatternSegments.RemoveAt(index);
            NormalizeSequenceSegments();
            UpdateSegmentsList();
            ClearSegmentEditor();
        }

        private void OnAddSegment(object sender, EventArgs e)
        {
            NumberingSegmentDefinition segment = BuildSegmentFromEditor();
            if (segment == null)
            {
                return;
            }

            if (_currentScheme == null)
            {
                _currentScheme = new NumberingSchemeDefinition();
            }

            _currentScheme.PatternSegments.Add(segment);
            NormalizeSequenceSegments();
            UpdateSegmentsList();
            if (_segmentsList != null)
            {
                _segmentsList.SelectedIndex = _segmentsList.Items.Count - 1;
            }
        }

        private void OnUpdateSegment(object sender, EventArgs e)
        {
            if (_segmentsList == null || _currentScheme == null)
            {
                return;
            }

            int index = _segmentsList.SelectedIndex;
            if (index < 0 || index >= _currentScheme.PatternSegments.Count)
            {
                return;
            }

            NumberingSegmentDefinition segment = BuildSegmentFromEditor();
            if (segment == null)
            {
                return;
            }

            _currentScheme.PatternSegments[index] = segment;
            NormalizeSequenceSegments();
            UpdateSegmentsList();
            _segmentsList.SelectedIndex = index;
        }

        private void OnValidateScheme(object sender, EventArgs e)
        {
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            NumberingSchemeDefinition scheme = ReadSchemeFromUi();
            ApiResponse response = client.ValidateScheme(scheme);
            if (!response.Ok)
            {
                ShowApiError("Validation failed.", response);
                return;
            }

            Dictionary<string, object> example = NumberingJson.GetDict(response.Data, "example");
            string pn = example != null ? NumberingJson.GetString(example, "part_number_example") : string.Empty;
            string rev = example != null ? NumberingJson.GetString(example, "revision_example") : string.Empty;
            string msg = "Valid";
            if (!string.IsNullOrWhiteSpace(pn))
            {
                msg = "Valid: " + pn + (string.IsNullOrWhiteSpace(rev) ? "" : "-" + rev);
            }
            if (_validationResultLabel != null)
            {
                _validationResultLabel.Text = msg;
            }
        }

        private void OnSaveScheme(object sender, EventArgs e)
        {
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            NumberingSchemeDefinition scheme = ReadSchemeFromUi();
            ApiResponse response = string.IsNullOrWhiteSpace(scheme.Id)
                ? client.CreateScheme(scheme)
                : client.UpdateScheme(scheme);

            if (!response.Ok)
            {
                ShowApiError("Failed to save scheme.", response);
                return;
            }

            MessageBox.Show("Scheme saved.", "TinyMRP",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            Dictionary<string, object> schemeData = NumberingJson.GetDict(response.Data, "scheme");
            string savedId = schemeData != null ? NumberingJson.GetString(schemeData, "id") : scheme.Id;
            if (_schemeCombo != null && !string.IsNullOrWhiteSpace(savedId))
            {
                _schemeCombo.Tag = savedId;
            }
            OnRefreshSchemes(this, EventArgs.Empty);
        }

        private void OnDeactivateScheme(object sender, EventArgs e)
        {
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string schemeId = GetSelectedSchemeId();
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                MessageBox.Show("Select a scheme first.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            DialogResult confirmDelete = MessageBox.Show(
                "Delete this numbering scheme? This cannot be undone.",
                "TinyMRP",
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Warning);
            if (confirmDelete != DialogResult.Yes)
            {
                return;
            }

            ApiResponse response = client.DeleteScheme(schemeId);
            if (!response.Ok)
            {
                ShowApiError("Failed to delete scheme.", response);
                return;
            }

            MessageBox.Show("Scheme deleted.", "TinyMRP",
                MessageBoxButtons.OK, MessageBoxIcon.Information);
            OnRefreshSchemes(this, EventArgs.Empty);
        }

        private void OnPreviewNext(object sender, EventArgs e)
        {
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string schemeId = GetSelectedSchemeId();
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                MessageBox.Show("Select a scheme first.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ApiResponse response = client.Preview(schemeId, BuildContextFromUi());
            if (!response.Ok)
            {
                ShowApiError("Preview failed.", response);
                return;
            }

            string partNumber = NumberingJson.GetString(response.Data, "candidate_part_number");
            string revision = NumberingJson.GetString(response.Data, "candidate_revision");
            string display = NumberingJson.GetString(response.Data, "display_code_candidate");
            if (string.IsNullOrWhiteSpace(display))
            {
                display = BuildDisplayCode(partNumber, revision);
            }

            if (_previewResultLabel != null)
            {
                _previewResultLabel.Text = display;
            }
        }

        private void OnAllocateNumber(object sender, EventArgs e)
        {
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string schemeId = GetSelectedSchemeId();
            if (string.IsNullOrWhiteSpace(schemeId))
            {
                MessageBox.Show("Select a scheme first.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ISldWorks app = AddinContext.SldWorks;
            if (app == null)
            {
                MessageBox.Show("SolidWorks is not available.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ActiveModelInfo info;
            string error;
            if (!SolidWorksDocumentHelper.TryGetActiveModel(app, out info, out error))
            {
                MessageBox.Show(error, "TinyMRP", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            string action = GetComboText(_revisionActionCombo);
            string existingPartNumber = _existingPartNumberText != null ? _existingPartNumberText.Text.Trim() : string.Empty;
            if (string.IsNullOrWhiteSpace(existingPartNumber))
            {
                existingPartNumber = TryReadPartNumberFromActiveDoc();
            }

            if ((string.Equals(action, "revise_existing", StringComparison.OrdinalIgnoreCase) ||
                 string.Equals(action, "keep_existing", StringComparison.OrdinalIgnoreCase)) &&
                string.IsNullOrWhiteSpace(existingPartNumber))
            {
                MessageBox.Show("Existing part number is required for revision actions.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            bool createPart = _createPartCheck != null && _createPartCheck.Checked;
            ApiResponse response = client.Allocate(
                schemeId,
                BuildContextFromUi(),
                action,
                existingPartNumber,
                createPart,
                BuildCadRef(info));

            if (!response.Ok)
            {
                ShowApiError("Allocation failed.", response);
                return;
            }

            string partNumber = NumberingJson.GetString(response.Data, "part_number");
            string revision = NumberingJson.GetString(response.Data, "revision");
            if (string.IsNullOrWhiteSpace(partNumber))
            {
                MessageBox.Show("Allocation did not return a part number.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            // Explicit revision actions (revise/keep existing) apply the returned revision as-is;
            // plain new-part allocations must not stamp a default revision onto revision-less models.
            if (string.Equals(action, "new_part", StringComparison.OrdinalIgnoreCase) ||
                string.IsNullOrWhiteSpace(action))
            {
                revision = ResolveRevisionForApply(info, revision);
            }

            string display = NumberingJson.GetString(response.Data, "display_code");
            if (string.IsNullOrWhiteSpace(display) || string.IsNullOrWhiteSpace(revision))
            {
                display = BuildDisplayCode(partNumber, revision);
            }

            if (!ApplyNumberingToModel(info, partNumber, revision, display, schemeId))
            {
                return;
            }

            if (_existingPartNumberText != null)
            {
                _existingPartNumberText.Text = partNumber;
            }

            if (_allocateResultLabel != null)
            {
                _allocateResultLabel.Text = display;
            }
        }

        private void OnLoadConfigurations(object sender, EventArgs e)
        {
            if (_configListBox == null)
            {
                return;
            }

            ISldWorks app = AddinContext.SldWorks;
            if (app == null)
            {
                MessageBox.Show("SolidWorks is not available.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ActiveModelInfo info;
            string error;
            if (!SolidWorksDocumentHelper.TryGetActiveModel(app, out info, out error))
            {
                MessageBox.Show(error, "TinyMRP", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            List<string> configs = SolidWorksDocumentHelper.GetConfigurationNames(info.Model);
            _configListBox.Items.Clear();
            foreach (string name in configs)
            {
                _configListBox.Items.Add(name, string.Equals(name, info.ActiveConfiguration, StringComparison.OrdinalIgnoreCase));
            }

            if (info.StartedFromDrawing)
            {
                app.ActivateDoc(info.StartTitle);
            }
        }

        private void UpdateSegmentEditorState()
        {
            string kind = GetComboText(_segmentKindCombo).ToLowerInvariant();
            bool isLiteral = kind == "literal";
            bool isSeq = kind == "seq";
            bool isDate = kind == "date";
            bool seqIsAutomatic = _segmentSeqAutoCheck != null && _segmentSeqAutoCheck.Checked;

            if (_segmentLiteralText != null) _segmentLiteralText.Enabled = isLiteral;
            if (_segmentSeqPaddingUpDown != null) _segmentSeqPaddingUpDown.Enabled = isSeq;
            if (_segmentSeqBaseCombo != null) _segmentSeqBaseCombo.Enabled = isSeq;
            if (_segmentSeqStartUpDown != null) _segmentSeqStartUpDown.Enabled = isSeq && !seqIsAutomatic;
            if (_segmentSeqAutoCheck != null) _segmentSeqAutoCheck.Enabled = isSeq;
            if (_segmentDateFmtCombo != null) _segmentDateFmtCombo.Enabled = isDate;
        }

        private void ClearSegmentEditor()
        {
            SelectComboItem(_segmentKindCombo, "literal");
            _segmentLiteralText.Text = string.Empty;
            _segmentSeqPaddingUpDown.Value = 6;
            SelectComboItem(_segmentSeqBaseCombo, "10");
            if (_segmentSeqStartUpDown != null)
            {
                _segmentSeqStartUpDown.Value = _seqStartUpDown != null ? _seqStartUpDown.Value : 1;
            }
            if (_segmentSeqAutoCheck != null)
            {
                _segmentSeqAutoCheck.Checked = false;
            }
            SelectComboItem(_segmentDateFmtCombo, "YYYY");
            UpdateSegmentEditorState();
        }

        private NumberingSegmentDefinition BuildSegmentFromEditor()
        {
            string kind = GetComboText(_segmentKindCombo).ToLowerInvariant();
            if (string.IsNullOrWhiteSpace(kind))
            {
                MessageBox.Show("Select a segment kind.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return null;
            }

            var segment = new NumberingSegmentDefinition { Kind = kind };
            if (kind == "literal")
            {
                string value = _segmentLiteralText != null ? _segmentLiteralText.Text.Trim() : string.Empty;
                if (string.IsNullOrWhiteSpace(value))
                {
                    MessageBox.Show("Literal value is required.", "TinyMRP",
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return null;
                }
                segment.Value = value;
            }
            else if (kind == "seq")
            {
                int padding = (int)(_segmentSeqPaddingUpDown != null ? _segmentSeqPaddingUpDown.Value : 0);
                if (padding > 0)
                {
                    segment.Padding = padding;
                }
                int baseValue = ParseInt(GetComboText(_segmentSeqBaseCombo), 10);
                segment.Base = baseValue;
                if (_segmentSeqStartUpDown != null)
                {
                    segment.StartAt = (int)_segmentSeqStartUpDown.Value;
                }
                if (_segmentSeqAutoCheck != null)
                {
                    segment.AutoCounter = _segmentSeqAutoCheck.Checked;
                }
            }
            else if (kind == "date")
            {
                string fmt = GetComboText(_segmentDateFmtCombo);
                if (string.IsNullOrWhiteSpace(fmt))
                {
                    MessageBox.Show("Date format is required.", "TinyMRP",
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return null;
                }
                segment.Fmt = fmt;
            }

            return segment;
        }

        private void NormalizeSequenceSegments()
        {
            if (_currentScheme == null || _currentScheme.PatternSegments == null)
            {
                return;
            }

            List<NumberingSegmentDefinition> sequenceSegments = GetSequenceSegments(_currentScheme);
            if (sequenceSegments.Count == 0)
            {
                return;
            }

            int autoIndex = -1;
            for (int i = 0; i < sequenceSegments.Count; i++)
            {
                if (!sequenceSegments[i].AutoCounter)
                {
                    continue;
                }

                if (autoIndex < 0)
                {
                    autoIndex = i;
                }
                else
                {
                    sequenceSegments[i].AutoCounter = false;
                }
            }

            if (autoIndex < 0)
            {
                sequenceSegments[0].AutoCounter = true;
            }
        }

        private void UpdateSegmentsList()
        {
            if (_segmentsList == null)
            {
                return;
            }

            if (_currentScheme == null)
            {
                _currentScheme = new NumberingSchemeDefinition();
            }

            NormalizeSequenceSegments();

            _segmentsList.Items.Clear();
            foreach (NumberingSegmentDefinition segment in _currentScheme.PatternSegments)
            {
                _segmentsList.Items.Add(segment);
            }
        }

        private void ApplySchemeToUi(NumberingSchemeDefinition scheme)
        {
            if (scheme == null)
            {
                return;
            }

            if (_schemeNameText != null)
            {
                string name = scheme.Name ?? string.Empty;
                if (string.IsNullOrWhiteSpace(scheme.Id) &&
                    string.Equals(name, NumberingSchemeCatalog.NewSchemePlaceholderName, StringComparison.OrdinalIgnoreCase))
                {
                    name = string.Empty;
                }
                _schemeNameText.Text = name;
            }
            if (_schemeDescriptionText != null)
            {
                _schemeDescriptionText.Text = scheme.Description ?? string.Empty;
            }
            if (_schemeActiveCheck != null)
            {
                _schemeActiveCheck.Checked = scheme.IsActive;
            }
            if (_schemePresetCheck != null)
            {
                _schemePresetCheck.Checked = scheme.IsPreset;
            }
            if (_schemeRecommendedCheck != null)
            {
                _schemeRecommendedCheck.Checked = scheme.IsRecommended;
            }
            SelectComboItem(_schemeVisibilityCombo, string.IsNullOrWhiteSpace(scheme.Visibility) ? "advanced_only" : scheme.Visibility);
            if (_separatorText != null)
            {
                _separatorText.Text = scheme.Separator ?? "-";
            }
            SelectComboItem(_scopeModeCombo, scheme.ScopeMode);
            if (_scopeKeysText != null)
            {
                _scopeKeysText.Text = scheme.ScopeKeys != null ? string.Join(",", scheme.ScopeKeys) : string.Empty;
            }

            if (_seqPaddingUpDown != null)
            {
                _seqPaddingUpDown.Value = scheme.Seq != null ? scheme.Seq.Padding : _seqPaddingUpDown.Value;
            }
            SelectComboItem(_seqBaseCombo, scheme.Seq != null ? scheme.Seq.Base.ToString() : string.Empty);
            if (_seqStartUpDown != null)
            {
                _seqStartUpDown.Value = scheme.Seq != null ? scheme.Seq.StartAt : _seqStartUpDown.Value;
            }
            SelectComboItem(_seqResetCombo, scheme.Seq != null ? scheme.Seq.ResetPolicy : string.Empty);

            SelectComboItem(_revPolicyCombo, scheme.Revision != null ? scheme.Revision.Policy : "none");
            if (_revStartText != null)
            {
                _revStartText.Text = scheme.Revision != null ? (scheme.Revision.Start ?? string.Empty) : string.Empty;
            }

            if (_maxLengthUpDown != null)
            {
                _maxLengthUpDown.Value = scheme.ValidationRules != null ? scheme.ValidationRules.MaxLength : _maxLengthUpDown.Value;
            }
            if (_allowedCharsetText != null)
            {
                _allowedCharsetText.Text = scheme.ValidationRules != null ? scheme.ValidationRules.AllowedCharset : "A-Z0-9-";
            }
            if (_requireSeqCheck != null)
            {
                _requireSeqCheck.Checked = scheme.ValidationRules == null || scheme.ValidationRules.RequireSeqSegment;
            }

            UpdateSegmentsList();
        }

        private NumberingSchemeDefinition ReadSchemeFromUi()
        {
            var scheme = _currentScheme ?? new NumberingSchemeDefinition();
            scheme.Name = _schemeNameText != null ? _schemeNameText.Text.Trim() : scheme.Name;
            scheme.Description = _schemeDescriptionText != null ? _schemeDescriptionText.Text.Trim() : scheme.Description;
            scheme.IsActive = _schemeActiveCheck != null && _schemeActiveCheck.Checked;
            scheme.IsPreset = _schemePresetCheck != null && _schemePresetCheck.Checked;
            scheme.IsRecommended = _schemeRecommendedCheck != null && _schemeRecommendedCheck.Checked;
            string visibility = GetComboText(_schemeVisibilityCombo);
            scheme.Visibility = string.IsNullOrWhiteSpace(visibility) ? "advanced_only" : visibility;
            scheme.Separator = _separatorText != null ? _separatorText.Text.Trim() : "-";
            scheme.ScopeMode = GetComboText(_scopeModeCombo);
            scheme.ScopeKeys = ParseScopeKeys(_scopeKeysText != null ? _scopeKeysText.Text : string.Empty);

            scheme.Seq = new SequenceSettings
            {
                Padding = (int)(_seqPaddingUpDown != null ? _seqPaddingUpDown.Value : 6),
                Base = ParseInt(GetComboText(_seqBaseCombo), 10),
                StartAt = (int)(_seqStartUpDown != null ? _seqStartUpDown.Value : 1),
                ResetPolicy = GetComboText(_seqResetCombo)
            };

            scheme.Revision = new RevisionSettings
            {
                Policy = GetComboText(_revPolicyCombo),
                Start = _revStartText != null ? _revStartText.Text.Trim() : string.Empty
            };

            scheme.ValidationRules = new ValidationRules
            {
                MaxLength = (int)(_maxLengthUpDown != null ? _maxLengthUpDown.Value : 32),
                AllowedCharset = _allowedCharsetText != null ? _allowedCharsetText.Text.Trim() : "A-Z0-9-",
                RequireSeqSegment = _requireSeqCheck != null && _requireSeqCheck.Checked
            };

            scheme.PatternSegments = new List<NumberingSegmentDefinition>();
            if (_segmentsList != null)
            {
                foreach (object item in _segmentsList.Items)
                {
                    NumberingSegmentDefinition segment = item as NumberingSegmentDefinition;
                    if (segment != null)
                    {
                        scheme.PatternSegments.Add(segment);
                    }
                }
            }

            _currentScheme = scheme;
            NormalizeSequenceSegments();
            return _currentScheme;
        }

        private string GetSelectedSchemeId()
        {
            NumberingSchemeDefinition scheme = _schemeCombo != null
                ? _schemeCombo.SelectedItem as NumberingSchemeDefinition
                : null;
            if (scheme != null && !string.IsNullOrWhiteSpace(scheme.Id))
            {
                return scheme.Id;
            }
            return _currentScheme != null ? _currentScheme.Id : string.Empty;
        }

        private Dictionary<string, string> BuildContextFromUi()
        {
            return new Dictionary<string, string>();
        }

        private Dictionary<string, string> BuildContextFromQuickStart()
        {
            return new Dictionary<string, string>();
        }

        private Dictionary<string, string> BuildContextFromNumberingQuick()
        {
            return new Dictionary<string, string>();
        }

        private Dictionary<string, string> BuildPropertyMapFromQuickStart()
        {
            var map = new Dictionary<string, string>();
            map["part_number_prop"] = GetPreferredText(_quickPartNumberPropText, null, "PartNumber");
            map["revision_prop"] = GetPreferredText(_quickRevisionPropText, null, "Revision");
            map["display_code_prop"] = GetPreferredText(_quickDisplayCodePropText, null, "DisplayCode");
            return map;
        }

        private Dictionary<string, string> BuildPropertyMapFromAdvanced()
        {
            var map = new Dictionary<string, string>();
            map["part_number_prop"] = GetPreferredText(_partNumberPropText, null, "PartNumber");
            map["revision_prop"] = GetPreferredText(_revisionPropText, null, "Revision");
            map["display_code_prop"] = GetPreferredText(_displayCodePropText, null, "DisplayCode");
            return map;
        }

        private UserSettingsDefinition BuildUserSettingsFromQuickStart()
        {
            string schemeId = GetSchemeIdFromCombo(_quickSchemeCombo);
            var settings = new UserSettingsDefinition
            {
                DefaultSchemeId = schemeId,
                DefaultContext = BuildContextFromQuickStart(),
                PropertyMap = BuildPropertyMapFromQuickStart(),
                ApplyMode = ApplyModeFromCombo(_quickApplyModeCombo),
                ShowAdvanced = false
            };
            return settings;
        }

        private UserSettingsDefinition BuildUserSettingsFromAdvanced()
        {
            string schemeId = GetSchemeIdFromCombo(_advancedSchemeCombo);
            Dictionary<string, string> context;
            string error;
            if (!TryParseContextJson(_advancedContextJsonText != null ? _advancedContextJsonText.Text : string.Empty, out context, out error))
            {
                MessageBox.Show("Invalid context JSON: " + error, "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
                return null;
            }

            var settings = new UserSettingsDefinition
            {
                DefaultSchemeId = schemeId,
                DefaultContext = context,
                PropertyMap = BuildPropertyMapFromAdvanced(),
                ApplyMode = ApplyModeFromCombo(_advancedApplyModeCombo),
                ShowAdvanced = true
            };
            return settings;
        }

        private void ApplyUserSettings(UserSettingsDefinition settings)
        {
            if (settings == null)
            {
                return;
            }

            if (!string.IsNullOrWhiteSpace(settings.DefaultSchemeId))
            {
                if (_quickSchemeCombo != null)
                {
                    _quickSchemeCombo.Tag = settings.DefaultSchemeId;
                    SelectSchemeOrFallback(_quickSchemeCombo, settings.DefaultSchemeId, true);
                }
                if (_numberingPresetCombo != null)
                {
                    _numberingPresetCombo.Tag = settings.DefaultSchemeId;
                    SelectSchemeOrFallback(_numberingPresetCombo, settings.DefaultSchemeId, true);
                }
                if (_advancedSchemeCombo != null)
                {
                    _advancedSchemeCombo.Tag = settings.DefaultSchemeId;
                    SelectSchemeOrFallback(_advancedSchemeCombo, settings.DefaultSchemeId, false);
                }
                if (_schemeCombo != null)
                {
                    _schemeCombo.Tag = settings.DefaultSchemeId;
                    SelectSchemeOrFallback(_schemeCombo, settings.DefaultSchemeId, false);
                }
            }

            if (settings.DefaultContext != null && _advancedContextJsonText != null)
            {
                _advancedContextJsonText.Text = ContextToJson(settings.DefaultContext);
            }

            if (settings.PropertyMap != null)
            {
                settings.PropertyMap.TryGetValue("part_number_prop", out string partProp);
                settings.PropertyMap.TryGetValue("revision_prop", out string revProp);
                settings.PropertyMap.TryGetValue("display_code_prop", out string displayProp);

                if (_quickPartNumberPropText != null) _quickPartNumberPropText.Text = partProp ?? _quickPartNumberPropText.Text;
                if (_quickRevisionPropText != null) _quickRevisionPropText.Text = revProp ?? _quickRevisionPropText.Text;
                if (_quickDisplayCodePropText != null) _quickDisplayCodePropText.Text = displayProp ?? _quickDisplayCodePropText.Text;
                if (_numberingPartNumberPropText != null) _numberingPartNumberPropText.Text = partProp ?? _numberingPartNumberPropText.Text;
                if (_numberingRevisionPropText != null) _numberingRevisionPropText.Text = revProp ?? _numberingRevisionPropText.Text;
                if (_numberingDisplayCodePropText != null) _numberingDisplayCodePropText.Text = displayProp ?? _numberingDisplayCodePropText.Text;
                if (_partNumberPropText != null) _partNumberPropText.Text = partProp ?? _partNumberPropText.Text;
                if (_revisionPropText != null) _revisionPropText.Text = revProp ?? _revisionPropText.Text;
                if (_displayCodePropText != null) _displayCodePropText.Text = displayProp ?? _displayCodePropText.Text;
            }

            SelectApplyModeCombo(_quickApplyModeCombo, settings.ApplyMode);
            SelectApplyModeCombo(_advancedApplyModeCombo, settings.ApplyMode);
            SelectApplyModeCombo(_applyScopeCombo, settings.ApplyMode);

            UpdateQuickContextVisibility(_numberingPresetCombo != null
                ? _numberingPresetCombo.SelectedItem as NumberingSchemeDefinition
                : (_quickSchemeCombo != null ? _quickSchemeCombo.SelectedItem as NumberingSchemeDefinition : null));

            TinyMrpConfig config = AddinContext.Config;
            if (config != null)
            {
                if (!string.IsNullOrWhiteSpace(settings.DefaultSchemeId))
                {
                    config.NumberingSchemeId = settings.DefaultSchemeId;
                }
                config.NumberingContextDefaults = string.Empty;
                if (settings.PropertyMap != null)
                {
                    if (settings.PropertyMap.TryGetValue("part_number_prop", out string partProp))
                    {
                        config.PartNumberProperty = partProp;
                    }
                    if (settings.PropertyMap.TryGetValue("revision_prop", out string revProp))
                    {
                        config.RevisionProperty = revProp;
                    }
                    if (settings.PropertyMap.TryGetValue("display_code_prop", out string displayProp))
                    {
                        config.DisplayCodeProperty = displayProp;
                    }
                }
                config.NumberingApplyMode = settings.ApplyMode ?? config.NumberingApplyMode;
            }
        }

        private List<string> ParseScopeKeys(string data)
        {
            var result = new List<string>();
            if (string.IsNullOrWhiteSpace(data))
            {
                return result;
            }

            string[] parts = data.Split(new[] { ',', ';' }, StringSplitOptions.RemoveEmptyEntries);
            foreach (string part in parts)
            {
                string trimmed = part.Trim();
                if (!string.IsNullOrWhiteSpace(trimmed))
                {
                    result.Add(trimmed);
                }
            }
            return result;
        }

        private void SetConfigSelection(bool selected)
        {
            if (_configListBox == null)
            {
                return;
            }

            for (int i = 0; i < _configListBox.Items.Count; i++)
            {
                _configListBox.SetItemChecked(i, selected);
            }
        }

        private List<string> GetSelectedConfigNames()
        {
            var result = new List<string>();
            if (_configListBox == null)
            {
                return result;
            }

            foreach (object item in _configListBox.CheckedItems)
            {
                if (item != null)
                {
                    result.Add(item.ToString());
                }
            }
            return result;
        }

        private bool ApplyNumberingToModel(ActiveModelInfo info, string partNumber, string revision, string displayCode, string schemeId)
        {
            if (info == null || info.Model == null)
            {
                MessageBox.Show("Active document not found.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return false;
            }

            string scope = GetComboText(_applyScopeCombo);
            List<string> configs = BuildTargetConfigurations(info, scope);
            bool includeDocProps = _applyDocPropsCheck != null && _applyDocPropsCheck.Checked;

            if (configs.Count == 0 && !includeDocProps)
            {
                MessageBox.Show("Select at least one configuration or enable document properties.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return false;
            }

            string partProp = GetPreferredText(_numberingPartNumberPropText ?? _quickPartNumberPropText, _partNumberPropText,
                AddinContext.Config != null ? AddinContext.Config.PartNumberProperty : "PartNumber");
            string revProp = GetPreferredText(_numberingRevisionPropText ?? _quickRevisionPropText, _revisionPropText,
                AddinContext.Config != null ? AddinContext.Config.RevisionProperty : "Revision");
            string displayProp = GetPreferredText(_numberingDisplayCodePropText ?? _quickDisplayCodePropText, _displayCodePropText,
                AddinContext.Config != null ? AddinContext.Config.DisplayCodeProperty : "DisplayCode");

            SolidWorksPropertyWriter.ApplyNumbering(
                info.Model,
                configs,
                includeDocProps,
                partNumber,
                revision,
                displayCode,
                schemeId,
                partProp,
                revProp,
                displayProp);

            if (info.StartedFromDrawing)
            {
                ISldWorks app = AddinContext.SldWorks;
                if (app != null)
                {
                    app.ActivateDoc(info.StartTitle);
                }
            }

            return true;
        }

        private List<string> BuildTargetConfigurations(ActiveModelInfo info, string scope)
        {
            var configs = new List<string>();
            if (info == null || info.Model == null)
            {
                return configs;
            }

            string applyScope = scope ?? string.Empty;
            if (applyScope.StartsWith("All", StringComparison.OrdinalIgnoreCase))
            {
                configs.AddRange(SolidWorksDocumentHelper.GetConfigurationNames(info.Model));
            }
            else if (applyScope.StartsWith("Selected", StringComparison.OrdinalIgnoreCase))
            {
                configs.AddRange(GetSelectedConfigNames());
            }
            else
            {
                if (!string.IsNullOrWhiteSpace(info.ActiveConfiguration))
                {
                    configs.Add(info.ActiveConfiguration);
                }
            }

            return configs;
        }

        private string GetComboText(ComboBox combo)
        {
            if (combo == null)
            {
                return string.Empty;
            }

            if (combo.SelectedItem is string selectedString)
            {
                return selectedString;
            }

            if (combo.SelectedItem != null)
            {
                return combo.SelectedItem.ToString();
            }

            return combo.Text ?? string.Empty;
        }

        private void SelectComboItem(ComboBox combo, string value)
        {
            if (combo == null)
            {
                return;
            }

            if (string.IsNullOrWhiteSpace(value))
            {
                if (combo.Items.Count > 0 && combo.SelectedIndex < 0)
                {
                    combo.SelectedIndex = 0;
                }
                return;
            }

            string target = value.Trim();
            for (int i = 0; i < combo.Items.Count; i++)
            {
                object item = combo.Items[i];
                if (item == null)
                {
                    continue;
                }

                if (item is NumberingSchemeDefinition scheme)
                {
                    if (string.Equals(scheme.Id, target, StringComparison.OrdinalIgnoreCase) ||
                        string.Equals(scheme.Name, target, StringComparison.OrdinalIgnoreCase))
                    {
                        combo.SelectedIndex = i;
                        return;
                    }
                }
                else if (string.Equals(item.ToString(), target, StringComparison.OrdinalIgnoreCase))
                {
                    combo.SelectedIndex = i;
                    return;
                }
            }
        }

        private int ParseInt(string value, int fallback)
        {
            int parsed;
            return int.TryParse(value, out parsed) ? parsed : fallback;
        }

        private string TryReadPartNumberFromActiveDoc()
        {
            ISldWorks app = AddinContext.SldWorks;
            if (app == null)
            {
                return string.Empty;
            }

            ActiveModelInfo info;
            string error;
            if (!SolidWorksDocumentHelper.TryGetActiveModel(app, out info, out error))
            {
                return string.Empty;
            }

            string propName = AddinContext.Config != null ? AddinContext.Config.PartNumberProperty : "PartNumber";
            if (string.IsNullOrWhiteSpace(propName))
            {
                propName = "PartNumber";
            }
            string value = GetCustomProperty(info.Model, info.ActiveConfiguration, propName);
            if (string.IsNullOrWhiteSpace(value))
            {
                value = GetCustomProperty(info.Model, string.Empty, propName);
            }

            if (info.StartedFromDrawing)
            {
                app.ActivateDoc(info.StartTitle);
            }

            return value ?? string.Empty;
        }

        private string GetCustomProperty(ModelDoc2 model, string configName, string propertyName)
        {
            if (model == null || string.IsNullOrWhiteSpace(propertyName))
            {
                return string.Empty;
            }

            CustomPropertyManager manager = model.Extension.CustomPropertyManager[configName ?? string.Empty];
            string valOut;
            string resolved;
            manager.Get2(propertyName, out valOut, out resolved);
            if (!string.IsNullOrWhiteSpace(resolved))
            {
                return resolved;
            }
            return valOut ?? string.Empty;
        }

        // Models that do not already track a revision stay revision-less: a new-part allocation must
        // not stamp the scheme's default start revision (e.g. "A") onto them. The allocated revision
        // is only applied when the model (config or document level) already carries a revision value.
        private string ResolveRevisionForApply(ActiveModelInfo info, string allocatedRevision)
        {
            if (string.IsNullOrWhiteSpace(allocatedRevision) || info == null || info.Model == null)
            {
                return string.Empty;
            }

            string revProp = AddinContext.Config != null ? AddinContext.Config.RevisionProperty : "Revision";
            if (string.IsNullOrWhiteSpace(revProp))
            {
                revProp = "Revision";
            }

            string existing = GetCustomProperty(info.Model, info.ActiveConfiguration, revProp);
            if (string.IsNullOrWhiteSpace(existing))
            {
                existing = GetCustomProperty(info.Model, string.Empty, revProp);
            }

            if (string.IsNullOrWhiteSpace(existing))
            {
                AddinLogger.Write("Allocation revision \"" + allocatedRevision +
                    "\" not applied: model has no existing revision, keeping it revision-less.");
                return string.Empty;
            }

            return allocatedRevision;
        }

        private Dictionary<string, object> BuildCadRef(ActiveModelInfo info)
        {
            if (info == null || info.Model == null)
            {
                return null;
            }

            string docType = "unknown";
            int type = info.Model.GetType();
            if (type == (int)swDocumentTypes_e.swDocPART)
            {
                docType = "part";
            }
            else if (type == (int)swDocumentTypes_e.swDocASSEMBLY)
            {
                docType = "assembly";
            }
            else if (type == (int)swDocumentTypes_e.swDocDRAWING)
            {
                docType = "drawing";
            }

            return new Dictionary<string, object>
            {
                ["file_path"] = info.Model.GetPathName() ?? string.Empty,
                ["doc_type"] = docType,
                ["config_name"] = info.ActiveConfiguration ?? string.Empty,
            };
        }

        private string BuildDisplayCode(string partNumber, string revision)
        {
            if (string.IsNullOrWhiteSpace(revision))
            {
                return partNumber ?? string.Empty;
            }
            return (partNumber ?? string.Empty) + "-" + revision;
        }

        private void ShowApiError(string title, ApiResponse response)
        {
            HandleApiError(title, response, true);
        }

        private void ShowConnectionFailure(string message, ApiResponse response, string extraDetail)
        {
            string details = BuildApiErrorDetails(response, extraDetail);
            AddinLogger.Write("Connection failed: " + message);
            if (!string.IsNullOrWhiteSpace(details))
            {
                AddinLogger.Write(details);
            }
            SetNumberingStatus(message, Color.Maroon);
            ShowMessageWithDetails("Connection failed", message, details);
        }

        private void HandleApiError(string title, ApiResponse response, bool showDialog)
        {
            if (response == null)
            {
                if (showDialog)
                {
                    MessageBox.Show(title, "TinyMRP", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
                SetNumberingStatus(title, Color.Maroon);
                return;
            }

            string message = response.ErrorMessage ?? "Request failed.";
            string details = BuildApiErrorDetails(response, null);

            AddinLogger.Write(title + ": " + message);
            if (!string.IsNullOrWhiteSpace(details))
            {
                AddinLogger.Write(details);
            }

            SetNumberingStatus(title + " " + message, Color.Maroon);
            if (showDialog)
            {
                ShowMessageWithDetails(title, message, details);
            }
        }

        private string BuildApiErrorDetails(ApiResponse response, string extraDetail)
        {
            if (response == null)
            {
                return extraDetail ?? string.Empty;
            }

            var lines = new List<string>();
            if (!string.IsNullOrWhiteSpace(extraDetail))
            {
                lines.Add(extraDetail);
            }
            if (!string.IsNullOrWhiteSpace(response.RequestUrl))
            {
                lines.Add("Final URL: " + response.RequestUrl);
            }
            if (response.StatusCode > 0)
            {
                lines.Add("HTTP status: " + response.StatusCode.ToString());
            }
            if (!string.IsNullOrWhiteSpace(response.ErrorCode))
            {
                lines.Add("Error code: " + response.ErrorCode);
            }
            if (!string.IsNullOrWhiteSpace(response.ResponseSnippet))
            {
                lines.Add("Response snippet: " + response.ResponseSnippet);
            }
            if (response.ResponseIsHtml)
            {
                lines.Add("Reached an HTML page/login page instead of the JSON API.");
            }

            foreach (string detail in response.ErrorDetails)
            {
                if (!string.IsNullOrWhiteSpace(detail)
                    && !string.Equals(detail, response.ResponseSnippet, StringComparison.Ordinal)
                    && !lines.Contains(detail))
                {
                    lines.Add(detail);
                }
            }

            return string.Join(System.Environment.NewLine, lines.ToArray());
        }

        private void AddDiagnosticResult(List<string> details, string label, ApiResponse response, string statusText)
        {
            if (details == null)
            {
                return;
            }

            if (response == null)
            {
                details.Add(label + ": Failed");
                details.Add("Error: no response");
                details.Add(string.Empty);
                return;
            }

            details.Add(label + ": " + statusText);
            if (!string.IsNullOrWhiteSpace(response.RequestUrl))
            {
                details.Add("URL: " + response.RequestUrl);
            }
            if (response.StatusCode > 0)
            {
                details.Add("HTTP status: " + response.StatusCode.ToString());
            }
            if (!response.Ok && !string.IsNullOrWhiteSpace(response.ErrorCode))
            {
                details.Add("Error code: " + response.ErrorCode);
            }
            if (!response.Ok && !string.IsNullOrWhiteSpace(response.ErrorMessage))
            {
                details.Add("Message: " + response.ErrorMessage);
            }
            if ((!response.Ok || response.ResponseIsHtml) && !string.IsNullOrWhiteSpace(response.ResponseSnippet))
            {
                details.Add("Response snippet: " + response.ResponseSnippet);
            }
            if (response.ResponseIsHtml)
            {
                details.Add("Note: reached an HTML page/login page instead of the JSON API.");
            }
            details.Add(string.Empty);
        }

        private static bool ResponseHasErrorCode(ApiResponse response, string code)
        {
            return response != null
                && string.Equals(response.ErrorCode, code, StringComparison.OrdinalIgnoreCase);
        }

        private void ShowMessageWithDetails(string title, string message, string details)
        {
            if (string.IsNullOrWhiteSpace(details))
            {
                MessageBox.Show(message, title, MessageBoxButtons.OK, MessageBoxIcon.Information);
                return;
            }

            using (var dialog = new Form())
            using (var copyButton = new Button())
            using (var closeButton = new Button())
            using (var textBox = new TextBox())
            using (var messageLabel = new Label())
            {
                dialog.Text = title;
                dialog.StartPosition = FormStartPosition.CenterParent;
                dialog.Size = new Size(520, 360);
                dialog.MinimumSize = new Size(420, 300);

                messageLabel.Text = message;
                messageLabel.Dock = DockStyle.Top;
                messageLabel.AutoSize = false;
                messageLabel.Height = 50;
                messageLabel.Padding = new Padding(10, 10, 10, 0);

                textBox.Multiline = true;
                textBox.ReadOnly = true;
                textBox.ScrollBars = ScrollBars.Vertical;
                textBox.Dock = DockStyle.Fill;
                textBox.Text = details;

                var buttonPanel = new FlowLayoutPanel
                {
                    Dock = DockStyle.Bottom,
                    Height = 44,
                    FlowDirection = FlowDirection.RightToLeft,
                    Padding = new Padding(10, 6, 10, 6)
                };
                copyButton.Text = "Copy debug details";
                copyButton.AutoSize = true;
                copyButton.Click += (_, __) => Clipboard.SetText(details ?? string.Empty);
                closeButton.Text = "Close";
                closeButton.AutoSize = true;
                closeButton.Click += (_, __) => dialog.Close();
                buttonPanel.Controls.Add(closeButton);
                buttonPanel.Controls.Add(copyButton);

                dialog.Controls.Add(textBox);
                dialog.Controls.Add(buttonPanel);
                dialog.Controls.Add(messageLabel);
                dialog.ShowDialog(this);
            }
        }

        private void SetDeliverableChecks(bool value)
        {
            if (_pngModelCheck != null) _pngModelCheck.Checked = value;
            if (_stepCheck != null) _stepCheck.Checked = value;
            if (_edrCheck != null) _edrCheck.Checked = value;
            if (_threeMfCheck != null) _threeMfCheck.Checked = value;
            if (_plyCheck != null) _plyCheck.Checked = value;
            if (_stlCheck != null) _stlCheck.Checked = value;
            if (_pngDrawingCheck != null) _pngDrawingCheck.Checked = value;
            if (_pdfCheck != null) _pdfCheck.Checked = value;
            if (_dxfCheck != null) _dxfCheck.Checked = value;
            if (_edrDrawingCheck != null) _edrDrawingCheck.Checked = value;
        }

        private void SetHideFeatureChecks(bool value)
        {
            if (_hideOriginCheck != null) _hideOriginCheck.Checked = value;
            if (_hidePlaneCheck != null) _hidePlaneCheck.Checked = value;
            if (_hideAxisCheck != null) _hideAxisCheck.Checked = value;
            if (_hidePointCheck != null) _hidePointCheck.Checked = value;
            if (_hideCoordSysCheck != null) _hideCoordSysCheck.Checked = value;
            if (_hideSketch2DCheck != null) _hideSketch2DCheck.Checked = value;
            if (_hideSketch3DCheck != null) _hideSketch3DCheck.Checked = value;
            if (_hideSpline3DCheck != null) _hideSpline3DCheck.Checked = value;
            if (_hideCompositeCurveCheck != null) _hideCompositeCurveCheck.Checked = value;
            if (_hideHelixCheck != null) _hideHelixCheck.Checked = value;
            if (_hideEnvelopeCheck != null) _hideEnvelopeCheck.Checked = value;
        }

        private void Log(string message)
        {
            SetStatus(message);
            AddinLogger.Write(message);
            try
            {
                TinyMrpPublisher publisher = AddinContext.Publisher;
                if (publisher != null)
                {
                    string p = publisher.LastRunLogPath;
                    if (!string.IsNullOrWhiteSpace(p) && !string.Equals(p, _lastRunLogPath, StringComparison.OrdinalIgnoreCase))
                    {
                        UpdateRunLogLink(p);
                    }
                }
            }
            catch
            {
                // ignore
            }
        }

        private void UpdateRunLogLink(string path)
        {
            try
            {
                if (InvokeRequired)
                {
                    BeginInvoke(new Action<string>(UpdateRunLogLink), path);
                    return;
                }

                string next = path ?? string.Empty;
                if (string.Equals(next, _lastRunLogPath, StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }
                _lastRunLogPath = next;
                if (_openLogLink == null)
                {
                    return;
                }

                string p = _lastRunLogPath;
                bool show = !string.IsNullOrWhiteSpace(p) && File.Exists(p);
                _openLogLink.Visible = show;
                if (show)
                {
                    _openLogLink.Text = "Open log: " + Path.GetFileName(p);
                }
            }
            catch
            {
                // ignore UI errors
            }
        }

        private void TryOpenLastRunLog()
        {
            try
            {
                string p = _lastRunLogPath ?? string.Empty;
                if (string.IsNullOrWhiteSpace(p) || !File.Exists(p))
                {
                    return;
                }

                Process.Start(new ProcessStartInfo
                {
                    FileName = p,
                    UseShellExecute = true,
                });
            }
            catch
            {
                // non-intrusive: ignore open failures (path may be blocked by policy)
            }
        }

        private void ResetProgress(ProgressBar bar, Label label, string actionName)
        {
            UpdateProgress(bar, label, actionName, 0, 0);
        }

        private void UpdatePublishProgress(int current, int total)
        {
            UpdateProgress(_publishProgressBar, _publishProgressLabel, "Create files", current, total);
        }

        private void UpdateBomProgress(int current, int total)
        {
            UpdateProgress(_bomProgressBar, _bomProgressLabel, "Process BOM", current, total);
        }

        private void UpdateToolsProgress(int current, int total)
        {
            UpdateProgress(_toolsProgressBar, _toolsProgressLabel, _toolsActionName, current, total);
        }

        private void UpdateProgress(ProgressBar bar, Label label, string actionName, int current, int total)
        {
            if (bar == null || label == null)
            {
                return;
            }

            if (bar.InvokeRequired || label.InvokeRequired)
            {
                BeginInvoke(new Action<ProgressBar, Label, string, int, int>(UpdateProgress),
                    bar, label, actionName, current, total);
                return;
            }

            int pct = total > 0 ? (int)Math.Round((double)current / total * 100) : 0;
            if (pct < 0) pct = 0;
            if (pct > 100) pct = 100;

            bar.Value = pct;
            label.Text = total > 0
                ? string.Format("{0}: {1} / {2}", actionName, current, total)
                : actionName + ": idle";
            Application.DoEvents();
        }

        private void SetStatus(string message)
        {
            if (_actionStatusLabel != null)
            {
                if (_actionStatusLabel.InvokeRequired)
                {
                    _actionStatusLabel.BeginInvoke(new Action<string>(SetStatus), message);
                    return;
                }
                _actionStatusLabel.Text = message ?? string.Empty;
            }

            if (_toolsStatusLabel != null)
            {
                if (_toolsStatusLabel.InvokeRequired)
                {
                    _toolsStatusLabel.BeginInvoke(new Action<string>(SetStatus), message);
                    return;
                }
                _toolsStatusLabel.Text = message ?? string.Empty;
            }
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

        private static TableLayoutPanel CreateStackPanel()
        {
            var panel = new TableLayoutPanel
            {
                ColumnCount = 1,
                RowCount = 0,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Dock = DockStyle.Top,
                MinimumSize = new Size(240, 0),
                GrowStyle = TableLayoutPanelGrowStyle.AddRows
            };
            panel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));
            return panel;
        }

        private static void AddStackRow(TableLayoutPanel panel, Control control)
        {
            if (panel == null || control == null)
            {
                return;
            }

            control.Dock = DockStyle.Top;
            control.Margin = new Padding(0, 0, 0, 6);
            control.Anchor = AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Top;

            int row = panel.RowCount;
            panel.RowCount++;
            panel.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            panel.Controls.Add(control, 0, row);
        }

        private static void AddSection(TableLayoutPanel panel, Control control)
        {
            if (panel == null || control == null)
            {
                return;
            }

            control.Dock = DockStyle.Fill;
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

            if (content.Dock == DockStyle.None || content.Dock == DockStyle.Fill)
            {
                content.Dock = DockStyle.Top;
            }
            box.Controls.Add(content);
            return box;
        }

        private static Control CreateCollapsibleSection(string title, Control content, bool expanded)
        {
            var container = new Panel
            {
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Dock = DockStyle.Top
            };

            var header = new Button
            {
                Text = (expanded ? "v " : "> ") + title,
                AutoSize = true,
                Dock = DockStyle.Top,
                FlatStyle = FlatStyle.Flat,
                TextAlign = ContentAlignment.MiddleLeft,
                Height = 24
            };
            header.FlatAppearance.BorderSize = 0;

            var body = new Panel
            {
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Dock = DockStyle.Top,
                Visible = expanded,
                Padding = new Padding(6, 4, 6, 4)
            };

            if (content.Dock == DockStyle.None)
            {
                content.Dock = DockStyle.Top;
            }
            body.Controls.Add(content);

            header.Click += (_, __) =>
            {
                body.Visible = !body.Visible;
                header.Text = (body.Visible ? "v " : "> ") + title;
            };

            container.Controls.Add(body);
            container.Controls.Add(header);
            return container;
        }

        private static Button CreateCommandButton(string text, EventHandler onClick)
        {
            var btn = new Button
            {
                Text = text,
                AutoSize = true,
                Height = 32,
                Padding = new Padding(6, 4, 6, 4),
                Font = new Font("Segoe UI", 9F, FontStyle.Bold, GraphicsUnit.Point)
            };
            if (onClick != null)
            {
                btn.Click += onClick;
            }
            return btn;
        }

        private static CheckBox CreateCheckBox(string text, int maxWidth = 240)
        {
            var box = new CheckBox
            {
                Text = text,
                AutoSize = true,
                Margin = new Padding(0, 2, 0, 2)
            };
            if (maxWidth > 0)
            {
                box.MaximumSize = new Size(maxWidth, 0);
            }
            return box;
        }

        private static TextBox CreateReadOnlyPreview()
        {
            return new TextBox
            {
                ReadOnly = true,
                TabStop = false,
                Width = 220,
                MinimumSize = new Size(220, 24),
                Height = 24,
                Anchor = AnchorStyles.Left | AnchorStyles.Right,
                BorderStyle = BorderStyle.FixedSingle,
                BackColor = SystemColors.ControlLight,
                Text = string.Empty
            };
        }

        private static void AddProgressRow(TableLayoutPanel table, string labelText, ProgressBar bar, Label valueLabel)
        {
            int row = table.RowCount;
            table.RowCount++;
            table.RowStyles.Add(new RowStyle(SizeType.AutoSize));

            var label = new Label { Text = labelText, AutoSize = true, Anchor = AnchorStyles.Left };

            var panel = new TableLayoutPanel
            {
                ColumnCount = 1,
                RowCount = 2,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Dock = DockStyle.Fill
            };
            panel.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            panel.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            bar.Dock = DockStyle.Fill;
            valueLabel.Dock = DockStyle.Fill;
            panel.Controls.Add(bar, 0, 0);
            panel.Controls.Add(valueLabel, 0, 1);

            table.Controls.Add(label, 0, row);
            table.Controls.Add(panel, 1, row);
        }

        private static TableLayoutPanel CreateFormLayout()
        {
            var table = new TableLayoutPanel
            {
                ColumnCount = 2,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Dock = DockStyle.Fill,
                MinimumSize = new Size(240, 0)
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

        private static void SetFieldLabelVisible(TableLayoutPanel table, string labelText, bool visible)
        {
            if (table == null)
            {
                return;
            }

            foreach (Control control in table.Controls)
            {
                if (control is Label label && string.Equals(label.Text, labelText, StringComparison.OrdinalIgnoreCase))
                {
                    label.Visible = visible;
                }
            }
        }

        private static Control CreateFolderPicker(TextBox target, EventHandler onBrowse)
        {
            return CreateInlineField(target, CreateBrowseButton(onBrowse));
        }

        private static Control CreateFilePicker(TextBox target, EventHandler onBrowse)
        {
            return CreateInlineField(target, CreateBrowseButton(onBrowse));
        }

        private static Control CreateInlineField(Control primary, Control trailingControl)
        {
            var panel = new Panel { Dock = DockStyle.Fill, Height = 26 };
            primary.Dock = DockStyle.Fill;
            trailingControl.Dock = DockStyle.Right;
            panel.Controls.Add(primary);
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
