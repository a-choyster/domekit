/**
 * SSE connection manager with automatic reconnect.
 */

export class SSEManager {
  constructor(url, { onMessage, onError, reconnectMs = 3000 } = {}) {
    this._url = url;
    this._onMessage = onMessage;
    this._onError = onError;
    this._reconnectMs = reconnectMs;
    this._source = null;
    this._timer = null;
    this._active = false;
  }

  connect() {
    if (this._source) this.disconnect();
    this._active = true;
    this._source = new EventSource(this._url);

    this._source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this._onMessage?.(data);
      } catch { /* skip malformed */ }
    };

    this._source.onerror = () => {
      this._source.close();
      this._source = null;
      this._onError?.();
      if (this._active) {
        this._timer = setTimeout(() => this.connect(), this._reconnectMs);
      }
    };
  }

  disconnect() {
    this._active = false;
    if (this._timer) { clearTimeout(this._timer); this._timer = null; }
    if (this._source) { this._source.close(); this._source = null; }
  }

  get connected() {
    return this._source?.readyState === EventSource.OPEN;
  }
}
