using System;
using System.Diagnostics;
using System.Collections.Generic;
using System.Drawing;
using System.Runtime.InteropServices;
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
        private ProgressBar _publishProgressBar;
        private Label _publishProgressLabel;
        private ProgressBar _bomProgressBar;
        private Label _bomProgressLabel;
        private Label _actionStatusLabel;
        private Button _cancelButton;
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
        private ComboBox _schemeCombo;
        private Button _schemeRefreshButton;
        private TextBox _schemeNameText;
        private TextBox _schemeDescriptionText;
        private CheckBox _schemeActiveCheck;
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
        private ComboBox _segmentFieldCombo;
        private ComboBox _segmentCasingCombo;
        private NumericUpDown _segmentPadLeftUpDown;
        private TextBox _segmentPadCharText;
        private NumericUpDown _segmentSeqPaddingUpDown;
        private ComboBox _segmentSeqBaseCombo;
        private ComboBox _segmentDateFmtCombo;
        private Label _validationResultLabel;
        private TextBox _contextTypeText;
        private TextBox _contextFamilyText;
        private TextBox _contextSubfamilyText;
        private TextBox _contextProjectText;
        private TextBox _contextSiteText;
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

            var publishActions = new FlowLayoutPanel
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
            publishActions.Controls.Add(btnSelectAll);
            publishActions.Controls.Add(btnDeselectAll);
            publishActions.Controls.Add(btnCreate);
            AddSection(panel, CreateGroupBox("Publish actions", publishActions));

            var bomActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
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
            _cancelButton = new Button { Text = "Cancel current task", AutoSize = true };
            _cancelButton.Click += OnCancelCurrentTask;
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
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
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
            _hideOriginCheck = new CheckBox { Text = "Origin" };
            _hidePlaneCheck = new CheckBox { Text = "Reference planes" };
            _hideAxisCheck = new CheckBox { Text = "Reference axes" };
            _hidePointCheck = new CheckBox { Text = "Reference points" };
            _hideCoordSysCheck = new CheckBox { Text = "Coordinate systems" };
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
            _hideSketch2DCheck = new CheckBox { Text = "2D sketches" };
            _hideSketch3DCheck = new CheckBox { Text = "3D sketches" };
            _hideSpline3DCheck = new CheckBox { Text = "3D spline curves" };
            _hideCompositeCurveCheck = new CheckBox { Text = "Composite curves" };
            _hideHelixCheck = new CheckBox { Text = "Helix" };
            hideSketchPanel.Controls.Add(_hideSketch2DCheck);
            hideSketchPanel.Controls.Add(_hideSketch3DCheck);
            hideSketchPanel.Controls.Add(_hideSpline3DCheck);
            hideSketchPanel.Controls.Add(_hideCompositeCurveCheck);
            hideSketchPanel.Controls.Add(_hideHelixCheck);

            hideOptionsLayout.Controls.Add(hideRefPanel, 0, 0);
            hideOptionsLayout.Controls.Add(hideSketchPanel, 1, 0);

            var hideActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
                Dock = DockStyle.Fill,
                Padding = new Padding(0, 2, 0, 0)
            };
            _hideAllConfigsCheck = new CheckBox { Text = "All configurations", AutoSize = true };
            _hideEnvelopeCheck = new CheckBox { Text = "Hide envelope components", AutoSize = true };
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
            AddSection(panel, CreateGroupBox("Scheme", schemeLayout));

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
                "Preset 1: TYPE-SEQ6",
                "Preset 2: TYPE-YYYY-SEQ5",
                "Preset 3: FAM-SUB-SEQ6"
            });
            var btnApplyPreset = new Button { Text = "Apply preset", AutoSize = true };
            btnApplyPreset.Click += OnApplyPreset;
            presetPanel.Controls.Add(_presetCombo);
            presetPanel.Controls.Add(btnApplyPreset);
            AddSection(panel, CreateGroupBox("Presets", presetPanel));

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
                Dock = DockStyle.Fill
            };
            segmentListLayout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));
            segmentListLayout.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));

            _segmentsList = new ListBox { Height = 140, Dock = DockStyle.Fill };
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
            _segmentKindCombo.Items.AddRange(new object[] { "literal", "field", "seq", "date" });
            _segmentKindCombo.SelectedIndexChanged += (_, __) => UpdateSegmentEditorState();
            AddField(segmentForm, "Kind", _segmentKindCombo);
            _segmentLiteralText = new TextBox { Width = 200 };
            AddField(segmentForm, "Literal value", _segmentLiteralText);
            _segmentFieldCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 200 };
            _segmentFieldCombo.Items.AddRange(new object[] { "type", "family", "subfamily", "project", "site" });
            AddField(segmentForm, "Field", _segmentFieldCombo);
            _segmentCasingCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 200 };
            _segmentCasingCombo.Items.AddRange(new object[] { "upper", "lower", "none" });
            AddField(segmentForm, "Casing", _segmentCasingCombo);
            _segmentPadLeftUpDown = new NumericUpDown { Width = 80, Minimum = 0, Maximum = 20 };
            AddField(segmentForm, "Pad left", _segmentPadLeftUpDown);
            _segmentPadCharText = new TextBox { Width = 40 };
            AddField(segmentForm, "Pad char", _segmentPadCharText);
            _segmentSeqPaddingUpDown = new NumericUpDown { Width = 80, Minimum = 1, Maximum = 12, Value = 6 };
            AddField(segmentForm, "Seq padding", _segmentSeqPaddingUpDown);
            _segmentSeqBaseCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 80 };
            _segmentSeqBaseCombo.Items.AddRange(new object[] { "10", "36" });
            AddField(segmentForm, "Seq base", _segmentSeqBaseCombo);
            _segmentDateFmtCombo = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 120 };
            _segmentDateFmtCombo.Items.AddRange(new object[] { "YYYY", "YY", "MM", "YYYYMM" });
            AddField(segmentForm, "Date format", _segmentDateFmtCombo);

            var segmentActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
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
            AddField(seqLayout, "Start at", _seqStartUpDown);
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
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
                Dock = DockStyle.Fill
            };
            var btnValidate = new Button { Text = "Validate scheme", AutoSize = true };
            btnValidate.Click += OnValidateScheme;
            var btnSaveScheme = new Button { Text = "Save scheme", AutoSize = true };
            btnSaveScheme.Click += OnSaveScheme;
            _validationResultLabel = new Label { AutoSize = true, Text = "" };
            schemeActions.Controls.Add(btnValidate);
            schemeActions.Controls.Add(btnSaveScheme);
            schemeActions.Controls.Add(_validationResultLabel);
            AddSection(panel, CreateGroupBox("Scheme actions", schemeActions));

            var contextLayout = CreateFormLayout();
            _contextTypeText = new TextBox { Width = 140 };
            AddField(contextLayout, "Type", _contextTypeText);
            _contextFamilyText = new TextBox { Width = 140 };
            AddField(contextLayout, "Family", _contextFamilyText);
            _contextSubfamilyText = new TextBox { Width = 140 };
            AddField(contextLayout, "Subfamily", _contextSubfamilyText);
            _contextProjectText = new TextBox { Width = 140 };
            AddField(contextLayout, "Project", _contextProjectText);
            _contextSiteText = new TextBox { Width = 140 };
            AddField(contextLayout, "Site", _contextSiteText);

            var previewActions = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
                Dock = DockStyle.Fill
            };
            var btnPreview = new Button { Text = "Preview next", AutoSize = true };
            btnPreview.Click += OnPreviewNext;
            _previewResultLabel = new Label { AutoSize = true, Text = "" };
            var btnSaveDefaults = new Button { Text = "Save defaults", AutoSize = true };
            btnSaveDefaults.Click += OnSaveNumberingDefaults;
            previewActions.Controls.Add(btnPreview);
            previewActions.Controls.Add(btnSaveDefaults);
            previewActions.Controls.Add(_previewResultLabel);

            var previewWrap = new FlowLayoutPanel
            {
                FlowDirection = FlowDirection.TopDown,
                AutoSize = true,
                WrapContents = false,
                Dock = DockStyle.Fill
            };
            previewWrap.Controls.Add(contextLayout);
            previewWrap.Controls.Add(previewActions);
            AddSection(panel, CreateGroupBox("Context + preview", previewWrap));

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
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true,
                Dock = DockStyle.Fill
            };
            var btnAllocate = new Button { Text = "Allocate PN+REV", AutoSize = true };
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
            AddSection(panel, CreateGroupBox("Allocate", allocateWrap));

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
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = true
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

            InitializeNumberingDefaults();
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

            if (_authTokenText != null)
            {
                _authTokenText.Text = config.AuthToken ?? string.Empty;
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

            config.BomFolder = config.DeliverablesFolder;

            if (_weblinkText != null)
            {
                config.WebLink = _weblinkText.Text;
            }

            if (_backendUrlText != null)
            {
                config.BackendUrl = _backendUrlText.Text;
            }

            if (_authTokenText != null)
            {
                config.AuthToken = _authTokenText.Text;
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

            string schemeId = GetSelectedSchemeId();
            if (!string.IsNullOrWhiteSpace(schemeId))
            {
                config.NumberingSchemeId = schemeId;
            }

            config.NumberingContextDefaults = BuildContextDefaultsString();
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
            publisher.ProcessFiles(options, Log, UpdatePublishProgress);
            SetStatus("Done.");
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
            publisher.ProcessBom(options, Log, UpdateBomProgress);
            SetStatus("Done.");
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
                _currentScheme = new NumberingSchemeDefinition { IsActive = true };
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

            if (_segmentFieldCombo != null && _segmentFieldCombo.SelectedIndex < 0)
            {
                _segmentFieldCombo.SelectedIndex = 0;
            }

            if (_segmentCasingCombo != null && _segmentCasingCombo.SelectedIndex < 0)
            {
                _segmentCasingCombo.SelectedIndex = 0;
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
                OnRefreshSchemes(this, EventArgs.Empty);
            }
        }

        private void ApplyNumberingDefaults(TinyMrpConfig config)
        {
            if (config == null)
            {
                return;
            }

            Dictionary<string, string> defaults = ParseContextDefaults(config.NumberingContextDefaults);
            SetContextField(_contextTypeText, defaults, "type");
            SetContextField(_contextFamilyText, defaults, "family");
            SetContextField(_contextSubfamilyText, defaults, "subfamily");
            SetContextField(_contextProjectText, defaults, "project");
            SetContextField(_contextSiteText, defaults, "site");

            if (_schemeCombo != null && !string.IsNullOrWhiteSpace(config.NumberingSchemeId))
            {
                _schemeCombo.Tag = config.NumberingSchemeId;
                SelectComboItem(_schemeCombo, config.NumberingSchemeId);
            }

            if (_existingPartNumberText != null && string.IsNullOrWhiteSpace(_existingPartNumberText.Text))
            {
                string partNumber = TryReadPartNumberFromActiveDoc();
                if (!string.IsNullOrWhiteSpace(partNumber))
                {
                    _existingPartNumberText.Text = partNumber;
                }
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
            NumberingApiClient client = GetNumberingClient();
            if (client == null)
            {
                MessageBox.Show("Backend URL is not configured.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            TinyMrpConfig config = AddinContext.Config;
            if (config != null && string.IsNullOrWhiteSpace(config.AuthToken))
            {
                MessageBox.Show("Auth token is missing. Set it in Configuration to load schemes.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }

            ApiResponse response = client.ListSchemes(out List<NumberingSchemeDefinition> schemes);
            if (!response.Ok)
            {
                ShowApiError("Failed to load schemes.", response);
                return;
            }

            _loadedSchemes.Clear();
            _loadedSchemes.AddRange(schemes);

            if (_schemeCombo != null)
            {
                _schemeCombo.Items.Clear();
                _schemeCombo.Items.Add(new NumberingSchemeDefinition { Name = "(new scheme)", IsActive = true });
                foreach (NumberingSchemeDefinition scheme in _loadedSchemes)
                {
                    _schemeCombo.Items.Add(scheme);
                }

                string preferredId = _schemeCombo.Tag as string;
                if (string.IsNullOrWhiteSpace(preferredId))
                {
                    preferredId = AddinContext.Config != null ? AddinContext.Config.NumberingSchemeId : string.Empty;
                }

                if (!string.IsNullOrWhiteSpace(preferredId))
                {
                    SelectComboItem(_schemeCombo, preferredId);
                }
                else if (_schemeCombo.Items.Count > 0)
                {
                    _schemeCombo.SelectedIndex = 0;
                }
            }
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
                _currentScheme = new NumberingSchemeDefinition();
            }

            _currentScheme.PatternSegments.Clear();

            int presetIndex = _presetCombo != null ? _presetCombo.SelectedIndex : -1;
            if (presetIndex < 0)
            {
                presetIndex = 0;
            }

            if (presetIndex == 0)
            {
                _currentScheme.PatternSegments.Add(new NumberingSegmentDefinition { Kind = "field", Field = "type", Casing = "upper" });
                _currentScheme.PatternSegments.Add(new NumberingSegmentDefinition { Kind = "seq", Padding = 6, Base = 10 });
                _seqPaddingUpDown.Value = 6;
            }
            else if (presetIndex == 1)
            {
                _currentScheme.PatternSegments.Add(new NumberingSegmentDefinition { Kind = "field", Field = "type", Casing = "upper" });
                _currentScheme.PatternSegments.Add(new NumberingSegmentDefinition { Kind = "date", Fmt = "YYYY" });
                _currentScheme.PatternSegments.Add(new NumberingSegmentDefinition { Kind = "seq", Padding = 5, Base = 10 });
                _seqPaddingUpDown.Value = 5;
            }
            else
            {
                _currentScheme.PatternSegments.Add(new NumberingSegmentDefinition { Kind = "field", Field = "family", Casing = "upper" });
                _currentScheme.PatternSegments.Add(new NumberingSegmentDefinition { Kind = "field", Field = "subfamily", Casing = "upper" });
                _currentScheme.PatternSegments.Add(new NumberingSegmentDefinition { Kind = "seq", Padding = 6, Base = 10 });
                _seqPaddingUpDown.Value = 6;
            }

            if (_separatorText != null)
            {
                _separatorText.Text = "-";
            }

            if (_seqBaseCombo != null)
            {
                _seqBaseCombo.SelectedIndex = 0;
            }

            if (_seqResetCombo != null)
            {
                _seqResetCombo.SelectedIndex = 0;
            }

            if (_revPolicyCombo != null)
            {
                _revPolicyCombo.SelectedIndex = 0;
            }

            if (_revStartText != null)
            {
                _revStartText.Text = "A";
            }

            UpdateSegmentsList();
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
            SelectComboItem(_segmentFieldCombo, segment.Field);
            SelectComboItem(_segmentCasingCombo, segment.Casing);
            _segmentPadLeftUpDown.Value = segment.PadLeft.HasValue ? segment.PadLeft.Value : 0;
            _segmentPadCharText.Text = segment.PadChar ?? string.Empty;
            _segmentSeqPaddingUpDown.Value = segment.Padding.HasValue ? segment.Padding.Value : _segmentSeqPaddingUpDown.Value;
            SelectComboItem(_segmentSeqBaseCombo, segment.Base.HasValue ? segment.Base.Value.ToString() : string.Empty);
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
            string display = NumberingJson.GetString(response.Data, "display_code");
            if (string.IsNullOrWhiteSpace(display))
            {
                display = BuildDisplayCode(partNumber, revision);
            }

            if (string.IsNullOrWhiteSpace(partNumber))
            {
                MessageBox.Show("Allocation did not return a part number.", "TinyMRP",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
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
            bool isField = kind == "field";
            bool isSeq = kind == "seq";
            bool isDate = kind == "date";

            if (_segmentLiteralText != null) _segmentLiteralText.Enabled = isLiteral;
            if (_segmentFieldCombo != null) _segmentFieldCombo.Enabled = isField;
            if (_segmentCasingCombo != null) _segmentCasingCombo.Enabled = isField;
            if (_segmentPadLeftUpDown != null) _segmentPadLeftUpDown.Enabled = isField;
            if (_segmentPadCharText != null) _segmentPadCharText.Enabled = isField;
            if (_segmentSeqPaddingUpDown != null) _segmentSeqPaddingUpDown.Enabled = isSeq;
            if (_segmentSeqBaseCombo != null) _segmentSeqBaseCombo.Enabled = isSeq;
            if (_segmentDateFmtCombo != null) _segmentDateFmtCombo.Enabled = isDate;
        }

        private void ClearSegmentEditor()
        {
            SelectComboItem(_segmentKindCombo, "literal");
            _segmentLiteralText.Text = string.Empty;
            SelectComboItem(_segmentFieldCombo, "type");
            SelectComboItem(_segmentCasingCombo, "upper");
            _segmentPadLeftUpDown.Value = 0;
            _segmentPadCharText.Text = string.Empty;
            _segmentSeqPaddingUpDown.Value = 6;
            SelectComboItem(_segmentSeqBaseCombo, "10");
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
            else if (kind == "field")
            {
                string field = GetComboText(_segmentFieldCombo);
                if (string.IsNullOrWhiteSpace(field))
                {
                    MessageBox.Show("Field is required.", "TinyMRP",
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return null;
                }
                segment.Field = field;
                string casing = GetComboText(_segmentCasingCombo);
                if (!string.IsNullOrWhiteSpace(casing) && !string.Equals(casing, "none", StringComparison.OrdinalIgnoreCase))
                {
                    segment.Casing = casing;
                }
                int padLeft = (int)(_segmentPadLeftUpDown != null ? _segmentPadLeftUpDown.Value : 0);
                if (padLeft > 0)
                {
                    segment.PadLeft = padLeft;
                }
                string padChar = _segmentPadCharText != null ? _segmentPadCharText.Text.Trim() : string.Empty;
                if (!string.IsNullOrWhiteSpace(padChar))
                {
                    segment.PadChar = padChar;
                }
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
                    string.Equals(name, "(new scheme)", StringComparison.OrdinalIgnoreCase))
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

            SelectComboItem(_revPolicyCombo, scheme.Revision != null ? scheme.Revision.Policy : string.Empty);
            if (_revStartText != null)
            {
                _revStartText.Text = scheme.Revision != null ? scheme.Revision.Start : "A";
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
                Start = _revStartText != null ? _revStartText.Text.Trim() : "A"
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
            return scheme;
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
            var context = new Dictionary<string, string>();
            AddContextField(_contextTypeText, context, "type");
            AddContextField(_contextFamilyText, context, "family");
            AddContextField(_contextSubfamilyText, context, "subfamily");
            AddContextField(_contextProjectText, context, "project");
            AddContextField(_contextSiteText, context, "site");
            return context;
        }

        private void SetContextField(TextBox textBox, Dictionary<string, string> context, string key)
        {
            if (textBox == null || context == null)
            {
                return;
            }

            if (context.TryGetValue(key, out string value))
            {
                textBox.Text = value ?? string.Empty;
            }
        }

        private void AddContextField(TextBox textBox, Dictionary<string, string> context, string key)
        {
            if (textBox == null || context == null)
            {
                return;
            }

            string value = textBox.Text != null ? textBox.Text.Trim() : string.Empty;
            if (!string.IsNullOrWhiteSpace(value))
            {
                context[key] = value;
            }
        }

        private string BuildContextDefaultsString()
        {
            return string.Format(
                "type={0};family={1};subfamily={2};project={3};site={4}",
                _contextTypeText != null ? _contextTypeText.Text.Trim() : string.Empty,
                _contextFamilyText != null ? _contextFamilyText.Text.Trim() : string.Empty,
                _contextSubfamilyText != null ? _contextSubfamilyText.Text.Trim() : string.Empty,
                _contextProjectText != null ? _contextProjectText.Text.Trim() : string.Empty,
                _contextSiteText != null ? _contextSiteText.Text.Trim() : string.Empty);
        }

        private Dictionary<string, string> ParseContextDefaults(string data)
        {
            var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            if (string.IsNullOrWhiteSpace(data))
            {
                return values;
            }

            string[] parts = data.Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries);
            foreach (string part in parts)
            {
                string[] pair = part.Split(new[] { '=' }, 2);
                if (pair.Length == 2)
                {
                    values[pair[0].Trim()] = pair[1].Trim();
                }
            }

            return values;
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

            SolidWorksPropertyWriter.ApplyNumbering(
                info.Model,
                configs,
                includeDocProps,
                partNumber,
                revision,
                displayCode,
                schemeId);

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

            string value = GetCustomProperty(info.Model, info.ActiveConfiguration, "PartNumber");
            if (string.IsNullOrWhiteSpace(value))
            {
                value = GetCustomProperty(info.Model, string.Empty, "PartNumber");
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
            if (response == null)
            {
                MessageBox.Show(title, "TinyMRP", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            string message = response.ErrorMessage ?? "Request failed.";
            if (response.ErrorDetails.Count > 0)
            {
                message += "\n" + string.Join("\n", response.ErrorDetails.ToArray());
            }

            MessageBox.Show(message, title, MessageBoxButtons.OK, MessageBoxIcon.Error);
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
