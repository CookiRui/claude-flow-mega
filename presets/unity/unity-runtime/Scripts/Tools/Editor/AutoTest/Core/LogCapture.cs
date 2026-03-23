using System;
using System.Collections.Generic;
using UnityEngine;

namespace {root-namespace}.Tools.AutoTest
{
    public class LogCapture : IDisposable
    {
        public struct LogEntry
        {
            public LogType Type;
            public string Message;
            public string StackTrace;
            public float Timestamp;
        }

        private readonly List<LogEntry> _entries = new();
        private readonly float _startTime;
        private bool _disposed;

        public IReadOnlyList<LogEntry> Entries => _entries;

        public bool HasErrors
        {
            get
            {
                for (int i = 0; i < _entries.Count; i++)
                {
                    if (_entries[i].Type == LogType.Error || _entries[i].Type == LogType.Exception)
                        return true;
                }
                return false;
            }
        }

        public List<LogEntry> GetErrors()
        {
            var errors = new List<LogEntry>();
            for (int i = 0; i < _entries.Count; i++)
            {
                if (_entries[i].Type == LogType.Error || _entries[i].Type == LogType.Exception)
                    errors.Add(_entries[i]);
            }
            return errors;
        }

        public LogCapture()
        {
            _startTime = Time.realtimeSinceStartup;
            Application.logMessageReceived += OnLogMessage;
        }

        private void OnLogMessage(string message, string stackTrace, LogType type)
        {
            if (_disposed) return;
            // Ignore Unity's internal log noise
            if (type == LogType.Log) return;

            _entries.Add(new LogEntry
            {
                Type = type,
                Message = message,
                StackTrace = stackTrace,
                Timestamp = Time.realtimeSinceStartup - _startTime
            });
        }

        public void Clear() => _entries.Clear();

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            Application.logMessageReceived -= OnLogMessage;
        }
    }
}
