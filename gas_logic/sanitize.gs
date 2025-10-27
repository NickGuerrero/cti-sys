// Main Contrbutor: Sergio Zavala
// https://www.imperva.com/learn/application-security/html-injection/
const htmlInjection = `<img src=x onerror=alert('Injected!')>`;

const urlScriptInjection = `http://example.com/page.html?userInput=<script>alert('Injected!');</script>`;

const urlJsInjection = `http://example.com/page.html?redirect=javascript:alert('Injected!')`;

const urlCodeInjection = `http://example.com/page.html?code=alert('Injected!')`;

const sqlInjection = `const sqliTest = "password'; DROP TABLE users; --";`;

const safeResponse = `Hello, my name is Sergio Zavala! I am currently a senior at CSU Monterey Bay finishing up my last two semesters.`

const htmlAndScriptMap = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;'
};

const SQLKeywords = [
  'union\\s+select',
  'drop\\s+table',
  'insert\\s+into',
  'delete\\s+from',
  'update\\s+\\w+\\s+set',
  'exec\\s+xp_',
  'benchmark\\s*\\(',
  'sleep\\s*\\(',
  'pg_sleep\\s*\\('
];

const sqliDetectRegex = new RegExp('\\b(?:' + SQLKeywords.join('|') + ')\\b', 'i');

function sanitize(responseValue) {
  const RESPONSE_MAX = 1000;

  let result = responseValue;

  // Reject null responses 
  if (result == null) {
    return result;
  };

  result = result.trim();

  // Reject empty responses
  if (result == "") {
    return result;
  }

  // Normalize value (since special characters can be used, this may lead to errors when searching (names, emails, etc), so we normalize to standard unicode)
  // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/normalize
  result = result.normalize("NFC");

  // Strip control/zero width characters
  result = result.replace(/[\u0000-\u001F\u007F\u200B-\u200D\uFEFF]/g, '');
    
  // Malicious URLs
  // "javascript:..."
  if (/^\s*(?:javascript|data|vbscript)\s*:/i.test(result)) return "";

  // "?p=javascript:...""
  if (/(?:[?&]|^)[^=&#]+\=\s*(?:javascript|data|vbscript)\s*:/i.test(result)) return "";

  // (code, userInput, redirect)
  if (/(?:[?&]|^)(?:code|userInput|redirect)=/i.test(result)) return "";

  
  // Implement malicious SQL sanitization (-- and ;)
  // https://www.codecademy.com/learn/seasp-defending-node-applications-from-sql-injection-xss-csrf-attacks/modules/seasp-preventing-sql-injection-attacks/cheatsheet
  result = result.replace(/--.*$/gm, "");
  result = result.replace(/;/g, "");

  if (sqliDetectRegex.test(result)) {
    return ""; // suspicious
  }

  // Malicous response (Output sanitization: The primary defense) (script / html)
  result = result.replace(/[&<>"']/g, ch => htmlAndScriptMap[ch]);

  // Buffer overflows can be used for malicous attacks, so for safety we should have a cap for character length.
  // https://www.portnox.com/cybersecurity-101/what-is-a-buffer-overflow/#:~:text=A%20buffer%20overflow%20occurs%20when,vulnerabilities%20that%20attackers%20can%20exploit.
  if (result.length > RESPONSE_MAX) {
    return result.slice(0, RESPONSE_MAX);
  }

  return result;
}

function TestFunction() {
  console.log(sanitize(sqlInjection))
}