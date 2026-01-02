using System;
using System.IO;
using System.Text.Json;

namespace TinyMRP.SolidWorksAddin.Services
{
    public class TinyMrpTokenStore
    {
        private class TokenState
        {
            public string? BaseUrl { get; set; }
            public string? AuthToken { get; set; }
            public string? Email { get; set; }
            public string? FilesLocalRoot { get; set; }
            public string? FilesUrlPrefix { get; set; }
        }

        private readonly string _path;
        private TokenState _state = new();

        public TinyMrpTokenStore()
        {
            var folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "TinyMRP");
            Directory.CreateDirectory(folder);
            _path = Path.Combine(folder, "addin_state.json");
            Load();
        }

        public string? AuthToken
        {
            get => _state.AuthToken;
            set { _state.AuthToken = value; Save(); }
        }

        public string? Email
        {
            get => _state.Email;
            set { _state.Email = value; Save(); }
        }

        public string? BaseUrl
        {
            get => _state.BaseUrl;
            set { _state.BaseUrl = value; Save(); }
        }

        public string? FilesLocalRoot
        {
            get => _state.FilesLocalRoot;
            set { _state.FilesLocalRoot = value; Save(); }
        }

        public string? FilesUrlPrefix
        {
            get => _state.FilesUrlPrefix;
            set { _state.FilesUrlPrefix = value; Save(); }
        }

        public void Clear()
        {
            _state = new TokenState();
            Save();
        }

        private void Load()
        {
            try
            {
                if (!File.Exists(_path))
                {
                    return;
                }

                var json = File.ReadAllText(_path);
                var loaded = JsonSerializer.Deserialize<TokenState>(json);
                if (loaded != null)
                {
                    _state = loaded;
                }
            }
            catch
            {
                _state = new TokenState();
            }
        }

        private void Save()
        {
            try
            {
                var json = JsonSerializer.Serialize(_state, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(_path, json);
            }
            catch
            {
                // ignore persistence errors; the add-in will continue in-memory
            }
        }
    }
}
