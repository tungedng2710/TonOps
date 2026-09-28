import {HTTP} from '~/app.constants';

export const isFileserverUrl = (url: string) =>
  url?.startsWith(HTTP.FILE_BASE_URL);

export const resolveLocalFileserverUrl = (url: string, fileserverBase: string): string => {
  if (!url || !fileserverBase) return url;
  try {
    const source = new URL(url);
    const target = new URL(fileserverBase);
    if ((source.hostname === 'localhost' || source.hostname === '127.0.0.1') &&
        source.port === target.port && /^https?:$/.test(target.protocol)) {
      source.protocol = target.protocol;
      source.host = target.host;
      return source.toString();
    }
  } catch { /* Keep non-HTTP and malformed URLs unchanged. */ }
  return url;
};

export const convertToReverseProxy = (url: string) => {
  try {
    const u = new URL(url);
    if (!u.pathname.startsWith('/files')) {
      u.protocol = window.location.protocol;
      u.host = window.location.host;
      u.pathname = 'files' + u.pathname;
      return u.toString();
    }
  } catch {}
  return url;
};
