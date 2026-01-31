using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Windows.Forms;
using TinyMRP.SolidWorksAddin.Services;

namespace TinyMRP.SolidWorksAddin.UI
{
    internal sealed class AssociatedFilesDialog : Form
    {
        private readonly DataGridView _grid;
        private readonly Button _addButton;
        private readonly Button _removeButton;
        private readonly Button _okButton;
        private readonly Button _cancelButton;

        public List<AssociatedFileEntry> Files { get; private set; } = new List<AssociatedFileEntry>();

        public AssociatedFilesDialog(IEnumerable<AssociatedFileEntry> initial)
        {
            Text = "Associated files";
            StartPosition = FormStartPosition.CenterParent;
            Size = new Size(720, 420);
            MinimizeBox = false;
            MaximizeBox = false;
            FormBorderStyle = FormBorderStyle.Sizable;

            _grid = new DataGridView
            {
                Dock = DockStyle.Fill,
                AllowUserToAddRows = false,
                AllowUserToDeleteRows = false,
                SelectionMode = DataGridViewSelectionMode.FullRowSelect,
                MultiSelect = true,
                AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
                RowHeadersVisible = false
            };

            var pathCol = new DataGridViewTextBoxColumn
            {
                HeaderText = "Path",
                ReadOnly = true,
                FillWeight = 70f
            };
            var labelCol = new DataGridViewTextBoxColumn
            {
                HeaderText = "Label",
                ReadOnly = false,
                FillWeight = 30f
            };
            _grid.Columns.Add(pathCol);
            _grid.Columns.Add(labelCol);

            if (initial != null)
            {
                foreach (AssociatedFileEntry entry in initial)
                {
                    if (entry == null || string.IsNullOrWhiteSpace(entry.Path))
                    {
                        continue;
                    }
                    _grid.Rows.Add(entry.Path, entry.Label ?? string.Empty);
                }
            }

            _addButton = new Button { Text = "Add files...", AutoSize = true };
            _removeButton = new Button { Text = "Remove selected", AutoSize = true };
            _okButton = new Button { Text = "OK", AutoSize = true, DialogResult = DialogResult.OK };
            _cancelButton = new Button { Text = "Cancel", AutoSize = true, DialogResult = DialogResult.Cancel };

            _addButton.Click += OnAddFiles;
            _removeButton.Click += OnRemoveSelected;
            _okButton.Click += (_, __) => Files = ReadFiles();

            AcceptButton = _okButton;
            CancelButton = _cancelButton;

            var buttons = new FlowLayoutPanel
            {
                Dock = DockStyle.Fill,
                FlowDirection = FlowDirection.LeftToRight,
                AutoSize = true,
                WrapContents = false
            };
            buttons.Controls.Add(_addButton);
            buttons.Controls.Add(_removeButton);

            var actions = new FlowLayoutPanel
            {
                Dock = DockStyle.Fill,
                FlowDirection = FlowDirection.RightToLeft,
                AutoSize = true,
                WrapContents = false
            };
            actions.Controls.Add(_cancelButton);
            actions.Controls.Add(_okButton);

            var footer = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 2,
                RowCount = 1,
                AutoSize = true
            };
            footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50F));
            footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50F));
            footer.Controls.Add(buttons, 0, 0);
            footer.Controls.Add(actions, 1, 0);

            var root = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 2,
                Padding = new Padding(8)
            };
            root.RowStyles.Add(new RowStyle(SizeType.Percent, 100F));
            root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            root.Controls.Add(_grid, 0, 0);
            root.Controls.Add(footer, 0, 1);

            Controls.Add(root);
        }

        private void OnAddFiles(object sender, EventArgs e)
        {
            using (var dialog = new OpenFileDialog())
            {
                dialog.Multiselect = true;
                dialog.Title = "Select associated files";
                if (dialog.ShowDialog(this) != DialogResult.OK)
                {
                    return;
                }

                foreach (string path in dialog.FileNames)
                {
                    if (string.IsNullOrWhiteSpace(path))
                    {
                        continue;
                    }
                    _grid.Rows.Add(path, string.Empty);
                }
            }
        }

        private void OnRemoveSelected(object sender, EventArgs e)
        {
            foreach (DataGridViewRow row in _grid.SelectedRows.Cast<DataGridViewRow>().ToList())
            {
                if (!row.IsNewRow)
                {
                    _grid.Rows.Remove(row);
                }
            }
        }

        private List<AssociatedFileEntry> ReadFiles()
        {
            var list = new List<AssociatedFileEntry>();
            foreach (DataGridViewRow row in _grid.Rows)
            {
                string path = row.Cells[0].Value != null ? row.Cells[0].Value.ToString() : string.Empty;
                string label = row.Cells[1].Value != null ? row.Cells[1].Value.ToString() : string.Empty;
                if (string.IsNullOrWhiteSpace(path))
                {
                    continue;
                }
                list.Add(new AssociatedFileEntry { Path = path, Label = label });
            }
            return list;
        }
    }
}
