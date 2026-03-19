/* py-see-claude frontend */

let previousPids = new Set();
let expandedPid = null;
let defaultHomeDir = '/';

// ========================================
// Feature 8: Dark/Light Theme
// ========================================
function getThemeColors() {
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
  return {
    screenGlowWorking: isDark ? '#27c93f' : '#1a9a2a',
    screenGlowThinking: isDark ? '#ffbd2e' : '#e6a820',
    screenGlowIdle: isDark ? '#334' : '#bbc',
    textLinesWorking: isDark ? '#4ae84a' : '#2aaa2a',
    textLinesThinking: isDark ? '#ffe066' : '#d4a030',
    textLinesIdle: isDark ? '#445' : '#aab',
    desk: isDark ? '#8b6914' : '#c49a40',
    deskDark: isDark ? '#6b4f10' : '#a88030',
    deskSleep: isDark ? '#5a4410' : '#a08030',
    deskSleepDark: isDark ? '#4a3a0d' : '#907020',
    monitor: isDark ? '#222' : '#ccc',
    monitorInner: isDark ? '#1a1a2e' : '#ddd',
    monitorStand: isDark ? '#333' : '#bbb',
    monitorSleep: isDark ? '#1a1a1a' : '#bbb',
    monitorSleepInner: isDark ? '#111' : '#ccc',
    monitorSleepDot: isDark ? '#333' : '#999',
    keyboard: isDark ? '#2a2a2a' : '#bbb',
    keyboardKeys: isDark ? '#3a3a3a' : '#999',
    eyes: isDark ? '#222' : '#111',
    mouth: isDark ? '#222' : '#111',
    thoughtBubble: isDark ? '#fff' : '#fff',
    thoughtDotActive: isDark ? '#444' : '#444',
    thoughtDotInactive: isDark ? '#ccc' : '#ccc',
    thoughtText: isDark ? '#666' : '#666',
    zzzColor: isDark ? '#555' : '#999',
    chairLegColor: isDark ? '#333' : '#999',
    chairSleepColor: isDark ? '#2a2a2a' : '#aaa',
    chairSleepLeg: isDark ? '#222' : '#888',
    sparklineBg: isDark ? '#1a1a2e' : '#e8e8f0',
    sparklineCpu: isDark ? '#27c93f' : '#1a9a2a',
    sparklineMem: isDark ? '#cc7832' : '#cc7832',
  };
}

let currentTheme = localStorage.getItem('see-claude-theme') || 'dark';

function applyTheme(theme) {
  currentTheme = theme;
  if (theme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
  const btn = document.getElementById('theme-btn');
  if (btn) btn.textContent = theme === 'light' ? '\u2600' : '\u263E';
  localStorage.setItem('see-claude-theme', theme);
}

function toggleTheme() {
  applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
  if (lastData && currentView === 'pixel') renderPixel(lastData.live);
}

applyTheme(currentTheme);

// ========================================
// Feature 2: Session Filtering/Search
// ========================================
let searchQuery = '';

document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      searchQuery = searchInput.value.toLowerCase().trim();
      if (lastData) {
        if (currentView === 'terminal') renderLive(lastData.live);
        else renderPixel(lastData.live);
        renderRecent(lastData.recent);
      }
    });
  }
});

function matchesSearch(session) {
  if (!searchQuery) return true;
  const fields = [
    session.projectName || '',
    session.status || '',
    session.cwd || '',
    ...(session.messages || []).map(m => m.text || ''),
  ];
  return fields.some(f => f.toLowerCase().includes(searchQuery));
}

function matchesSearchRecent(session) {
  if (!searchQuery) return true;
  const fields = [
    session.projectName || '',
    session.cwd || '',
    session.firstMessage || '',
  ];
  return fields.some(f => f.toLowerCase().includes(searchQuery));
}

// ========================================
// Feature 3: Resource Usage Graphs (Sparklines)
// ========================================
const MAX_SPARKLINE_POINTS = 60;
const resourceHistory = {};

function recordResourceHistory(sessions) {
  const activePids = new Set();
  sessions.forEach(s => {
    activePids.add(s.pid);
    if (!resourceHistory[s.pid]) {
      resourceHistory[s.pid] = { cpu: [], mem: [] };
    }
    const h = resourceHistory[s.pid];
    const cpuVal = parseFloat(s.cpu) || 0;
    const memVal = parseFloat(s.mem) || 0;
    h.cpu.push(cpuVal);
    h.mem.push(memVal);
    if (h.cpu.length > MAX_SPARKLINE_POINTS) h.cpu.shift();
    if (h.mem.length > MAX_SPARKLINE_POINTS) h.mem.shift();
  });
  // Clean up old entries
  for (const pid of Object.keys(resourceHistory)) {
    if (!activePids.has(pid)) {
      delete resourceHistory[pid];
    }
  }
}

function drawSparkline(canvas, data, color) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  const tc = getThemeColors();
  ctx.clearRect(0, 0, w, h);

  // Background
  ctx.fillStyle = tc.sparklineBg;
  ctx.fillRect(0, 0, w, h);

  if (!data || data.length < 2) return;

  const max = Math.max(...data, 1);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let i = 0; i < data.length; i++) {
    const x = (i / (data.length - 1)) * w;
    const y = h - (data[i] / max) * (h - 2) - 1;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

function renderSparklines(pid) {
  const h = resourceHistory[pid];
  if (!h) return;
  const tc = getThemeColors();
  const cpuCanvas = document.getElementById('spark-cpu-' + pid);
  const memCanvas = document.getElementById('spark-mem-' + pid);
  if (cpuCanvas) drawSparkline(cpuCanvas, h.cpu, tc.sparklineCpu);
  if (memCanvas) drawSparkline(memCanvas, h.mem, tc.sparklineMem);
}

// ========================================
// Feature 4: Sound Alerts
// ========================================
let soundEnabled = localStorage.getItem('see-claude-sound') === 'true';

document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('sound-toggle');
  if (toggle) {
    toggle.checked = soundEnabled;
    toggle.addEventListener('change', () => {
      soundEnabled = toggle.checked;
      localStorage.setItem('see-claude-sound', soundEnabled);
    });
  }
});

function playChime() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const now = ctx.currentTime;
    // First tone
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine';
    osc1.frequency.value = 523.25; // C5
    gain1.gain.setValueAtTime(0.15, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.4);
    // Second tone
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'sine';
    osc2.frequency.value = 659.25; // E5
    gain2.gain.setValueAtTime(0.15, now + 0.15);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.55);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.15);
    osc2.stop(now + 0.55);
    // Close context after sounds finish
    setTimeout(() => ctx.close(), 600);
  } catch (e) {
    // Web Audio API not available
  }
}

// ========================================
// Feature 7: Session Grouping
// ========================================
let sessionGroups = JSON.parse(localStorage.getItem('see-claude-groups') || '{}');
let collapsedGroups = JSON.parse(localStorage.getItem('see-claude-collapsed-groups') || '{}');
let groupModalCwd = null;

function getAutoGroup(cwd) {
  // Check custom groups first
  for (const [groupName, cwds] of Object.entries(sessionGroups)) {
    if (cwds.includes(cwd)) return groupName;
  }
  // Auto-group by parent directory
  const parts = cwd.split('/').filter(Boolean);
  if (parts.length >= 2) {
    return parts[parts.length - 2];
  }
  return 'Other';
}

function groupSessions(sessions) {
  const groups = {};
  sessions.forEach(s => {
    const group = getAutoGroup(s.cwd);
    if (!groups[group]) groups[group] = [];
    groups[group].push(s);
  });
  return groups;
}

function toggleGroup(groupName) {
  collapsedGroups[groupName] = !collapsedGroups[groupName];
  localStorage.setItem('see-claude-collapsed-groups', JSON.stringify(collapsedGroups));
  if (lastData) renderLive(lastData.live);
}

function openGroupModal(cwd, event) {
  if (event) { event.stopPropagation(); event.preventDefault(); }
  groupModalCwd = cwd;
  const input = document.getElementById('group-name-input');
  // Find current group
  let currentGroup = '';
  for (const [gn, cwds] of Object.entries(sessionGroups)) {
    if (cwds.includes(cwd)) { currentGroup = gn; break; }
  }
  input.value = currentGroup;
  document.getElementById('group-modal').classList.add('visible');
  setTimeout(() => input.focus(), 100);
}

function closeGroupModal() {
  document.getElementById('group-modal').classList.remove('visible');
  groupModalCwd = null;
}

function saveGroup() {
  const name = document.getElementById('group-name-input').value.trim();
  if (!groupModalCwd) { closeGroupModal(); return; }

  // Remove from all existing groups
  for (const [gn, cwds] of Object.entries(sessionGroups)) {
    sessionGroups[gn] = cwds.filter(c => c !== groupModalCwd);
    if (sessionGroups[gn].length === 0) delete sessionGroups[gn];
  }

  // Add to new group if name provided
  if (name) {
    if (!sessionGroups[name]) sessionGroups[name] = [];
    sessionGroups[name].push(groupModalCwd);
  }

  localStorage.setItem('see-claude-groups', JSON.stringify(sessionGroups));
  closeGroupModal();
  if (lastData) renderLive(lastData.live);
}

// ========================================
// Feature 5: Multi-Machine Support
// ========================================
let remoteConfig = null;
let remoteData = {};

async function fetchRemoteConfig() {
  try {
    const r = await fetch('/api/config');
    remoteConfig = await r.json();
    if (remoteConfig.remotes && remoteConfig.remotes.length > 0) {
      setInterval(fetchRemoteData, 5000);
      fetchRemoteData();
    }
  } catch (e) {
    // Config endpoint not available or no remotes
  }
}

async function fetchRemoteData() {
  if (!remoteConfig || !remoteConfig.remotes) return;
  for (const remote of remoteConfig.remotes) {
    try {
      const r = await fetch(`http://${remote.host}:${remote.port}/api/sessions`);
      const data = await r.json();
      remoteData[remote.name] = data;
    } catch (e) {
      // Remote unreachable
    }
  }
  // Re-render with merged data
  if (lastData) {
    if (currentView === 'terminal') renderLive(getMergedLive());
    else renderPixel(getMergedLive());
    renderRecent(getMergedRecent());
  }
}

function getMergedLive() {
  const local = (lastData?.live || []).map(s => ({ ...s, _machine: 'local' }));
  const remote = [];
  for (const [name, data] of Object.entries(remoteData)) {
    (data.live || []).forEach(s => {
      remote.push({ ...s, _machine: name, pid: name + ':' + s.pid, tty: name + ':' + s.tty });
    });
  }
  return [...local, ...remote];
}

function getMergedRecent() {
  const local = (lastData?.recent || []).map(s => ({ ...s, _machine: 'local' }));
  const remote = [];
  for (const [name, data] of Object.entries(remoteData)) {
    (data.recent || []).forEach(s => {
      remote.push({ ...s, _machine: name });
    });
  }
  return [...local, ...remote].sort((a, b) => b.lastModified - a.lastModified).slice(0, 30);
}

function machineBadgeHtml(session) {
  if (!session._machine || session._machine === 'local') return '';
  return ` <span class="machine-badge">${escapeHtml(session._machine)}</span>`;
}

// ========================================
// Core helpers
// ========================================
function getStatusLabel(s) { return s === 'working' ? 'Working' : s === 'thinking' ? 'Thinking' : 'Idle'; }
function getStatusColor(s) { return s === 'working' ? '#27c93f' : s === 'thinking' ? '#ffbd2e' : '#555'; }

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

// ========================================
// Render live sessions (terminal view)
// ========================================
function renderLive(sessions) {
  const grid = document.getElementById('grid');
  const groupedGrid = document.getElementById('grouped-grid');

  const filtered = sessions.filter(matchesSearch);
  document.getElementById('count').textContent = sessions.length;

  if (!filtered.length) {
    grid.innerHTML = '<div style="color:var(--text-stat-label);font-size:13px;padding:30px;text-align:center">No Claude sessions running</div>';
    groupedGrid.innerHTML = '';
    previousPids = new Set();
    return;
  }

  const currentPids = new Set(sessions.map(s => s.pid));
  const newPids = sessions.filter(s => !previousPids.has(s.pid)).map(s => s.pid);

  // Group sessions
  const groups = groupSessions(filtered);
  const groupNames = Object.keys(groups).sort();

  if (groupNames.length > 1) {
    // Render grouped view
    grid.innerHTML = '';
    groupedGrid.innerHTML = groupNames.map(groupName => {
      const isCollapsed = collapsedGroups[groupName];
      const groupSessions = groups[groupName];
      return `
        <div class="group-section">
          <div class="group-header" onclick="toggleGroup('${escapeHtml(groupName)}')">
            <span class="group-arrow ${isCollapsed ? 'collapsed' : ''}">\u25BC</span>
            ${escapeHtml(groupName)} (${groupSessions.length})
          </div>
          <div class="group-body ${isCollapsed ? 'collapsed' : ''}" style="${isCollapsed ? 'max-height:0' : 'max-height:9999px'}">
            <div class="group-grid">
              ${groupSessions.map(s => renderStationCard(s, newPids)).join('')}
            </div>
          </div>
        </div>
      `;
    }).join('');
  } else {
    // Single group or no grouping needed
    groupedGrid.innerHTML = '';
    grid.innerHTML = filtered.map(s => renderStationCard(s, newPids)).join('');
  }

  if (expandedPid) {
    const hist = document.getElementById('history-' + expandedPid);
    if (hist) hist.scrollTop = hist.scrollHeight;
  }

  // Draw sparklines after DOM is updated
  filtered.forEach(s => renderSparklines(s.pid));

  previousPids = currentPids;
}

function renderStationCard(s, newPids) {
  const isNew = newPids.includes(s.pid);
  const isExpanded = expandedPid === s.pid;
  const lastMsg = s.messages?.length ? s.messages[s.messages.length - 1] : null;

  let msgHtml = '';
  if (s.messages?.length) {
    msgHtml = s.messages.map(m => `
      <div class="msg-bubble ${m.role}">
        <span class="msg-role">${m.role === 'assistant' ? 'Claude' : 'You'}</span>
        <div class="msg-text">${escapeHtml(m.text)}</div>
      </div>
    `).join('');
  }

  const isRemote = s._machine && s._machine !== 'local';
  const realPid = isRemote ? s.pid.split(':').slice(1).join(':') : s.pid;
  const realTty = isRemote ? s.tty.split(':').slice(1).join(':') : s.tty;

  return `
  <div class="station ${s.status} ${isNew ? 'entering' : ''} ${isExpanded ? 'expanded' : ''}" data-pid="${s.pid}" onclick="handleClick('${s.pid}', '${s.tty}', event)">
    <button class="group-tag-btn" onclick="openGroupModal('${escapeHtml(s.cwd)}', event)" title="Set group">\u{1F3F7}</button>
    <div class="monitor">
      <div class="screen">
        <div class="screen-header">
          <div class="dot red"></div>
          <div class="dot yellow"></div>
          <div class="dot green"></div>
          <span class="screen-status" style="color:${getStatusColor(s.status)}">${getStatusLabel(s.status)}${machineBadgeHtml(s)}</span>
        </div>
        <div class="project-name">${escapeHtml(s.projectName)}</div>
        <div class="project-path">${escapeHtml(s.cwd)}</div>
        ${s.messages?.length && s.messages[0].role === 'user' ? `<div class="first-prompt">${escapeHtml(s.messages[0].text.slice(0, 80))}</div>` : ''}
        ${lastMsg ? `<div class="last-msg-preview"><span class="msg-label ${lastMsg.role === 'assistant' ? 'claude' : 'you'}">${lastMsg.role === 'assistant' ? 'Claude:' : 'You:'}</span> ${escapeHtml(lastMsg.text)}</div>` : ''}
        <div class="expanded-content">
          <div class="msg-history" id="history-${s.pid}">${msgHtml}</div>
          <div class="expanded-actions">
            <input class="chat-input" id="input-${s.pid}" placeholder="send a message..." onkeydown="if(event.key==='Enter')sendMsg('${realTty}','${s.pid}','${escapeHtml(s.cwd)}',event)" onclick="event.stopPropagation()">
            <button class="btn btn-send" onclick="sendMsg('${realTty}','${s.pid}','${escapeHtml(s.cwd)}',event)" onmousedown="event.preventDefault()">send</button>
            <button class="btn btn-terminal" onclick="openHistoryDialog('${escapeHtml(s.cwd)}','${escapeHtml(s.projectName)}','${realTty}','${s.pid}',event)">history</button>
            <button class="btn btn-close" onclick="collapseCard(event)">close</button>
            <span class="sent-flash" id="sent-${s.pid}">sent!</span>
          </div>
        </div>
        <div class="stats">
          <span><span class="stat-label">CPU</span> <span class="stat-value">${s.cpu}</span></span>
          <span><span class="stat-label">MEM</span> <span class="stat-value">${s.mem}</span></span>
          <span><span class="stat-label">UP</span> <span class="stat-value">${s.elapsed}</span></span>
        </div>
        <div class="sparkline-row">
          <span class="sparkline-label">cpu</span>
          <canvas class="sparkline-canvas" id="spark-cpu-${s.pid}" width="80" height="20"></canvas>
          <span class="sparkline-label">mem</span>
          <canvas class="sparkline-canvas" id="spark-mem-${s.pid}" width="80" height="20"></canvas>
        </div>
      </div>
    </div>
    <div class="stand"></div>
    <div class="base"></div>
    ${!isRemote ? `<button class="quick-terminal" onclick="openTerminal('${realTty}','${s.pid}','${escapeHtml(s.cwd)}',event)">&gt;_ terminal</button>` : ''}
  </div>
`;
}

function handleClick(pid, tty, event) {
  if (event.target.closest('.expanded-content') || event.target.closest('.btn') || event.target.closest('.quick-terminal') || event.target.closest('button') || event.target.closest('input')) return;

  if (expandedPid === pid) {
    expandedPid = null;
  } else {
    expandedPid = pid;
  }
  if (lastData) {
    renderLive(getMergedLive());
    setTimeout(() => {
      if (expandedPid) {
        const hist = document.getElementById('history-' + expandedPid);
        if (hist) hist.scrollTop = hist.scrollHeight;
        const input = document.getElementById('input-' + expandedPid);
        if (input) input.focus();
      }
    }, 50);
  }
}

function collapseCard(event) {
  event.stopPropagation();
  expandedPid = null;
  if (lastData) renderLive(getMergedLive());
}

async function sendMsg(tty, pid, cwd, event) {
  event.stopPropagation();
  const input = document.getElementById('input-' + pid);
  const msg = input.value.trim();
  if (!msg) return;

  try {
    const res = await fetch('/api/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tty, message: msg, cwd: cwd || '' }),
    });
    const data = await res.json();
    if (data.ok) {
      input.value = '';
      const sent = document.getElementById('sent-' + pid);
      sent.textContent = 'sent to terminal!';
      sent.classList.add('visible');
      setTimeout(() => sent.classList.remove('visible'), 2500);
    } else {
      showToast('Failed to send: ' + (data.error || 'unknown'));
    }
  } catch (e) { showToast('Failed to send'); }
}

async function openTerminal(tty, pid, cwd, event) {
  event.stopPropagation();
  try { await fetch('/api/focus?tty=' + encodeURIComponent(tty) + '&pid=' + encodeURIComponent(pid) + '&cwd=' + encodeURIComponent(cwd || '')); } catch (e) { /* ignore */ }
}

function renderRecent(sessions) {
  const tbody = document.getElementById('recent-body');
  if (!tbody) return;
  const liveDirs = new Set((lastData?.live || []).map(l => l.cwd));
  const filtered = sessions.filter(matchesSearchRecent);

  tbody.innerHTML = filtered.map(s => {
    const isLive = liveDirs.has(s.cwd);
    return `
    <tr class="recent-row ${isLive ? 'recent-live' : ''}">
      <td class="recent-project">${isLive ? '<span style="color:#27c93f;margin-right:4px">\u25CF</span>' : ''}${escapeHtml(s.projectName)}${machineBadgeHtml(s)}</td>
      <td class="recent-message">${escapeHtml(s.firstMessage)}</td>
      <td class="recent-time">${s.lastModifiedStr}</td>
      <td><div class="btn-group">
        <button class="resume-btn" onclick="copyResume('${s.sessionId}',event)" title="Copy claude --resume command to clipboard">copy cmd</button>
        <button class="launch-btn" onclick="launchResume('${s.sessionId}','${escapeHtml(s.cwd)}',event)" title="Open in a new Terminal tab">resume</button>
      </div></td>
    </tr>
  `}).join('');
}

function getResumeCmd(id) {
  let cmd = 'claude --resume ' + id;
  if (document.getElementById('skip-perms-toggle')?.checked) cmd += ' --dangerously-skip-permissions';
  return cmd;
}
function copyResume(id, e) {
  e.stopPropagation();
  const cmd = getResumeCmd(id);
  navigator.clipboard.writeText(cmd).then(() => showToast('Copied: ' + cmd)).catch(() => showToast('Copy failed'));
}
async function launchResume(id, cwd, e) {
  e.stopPropagation();
  const skip = document.getElementById('skip-perms-toggle')?.checked;
  try {
    const r = await fetch('/api/launch', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({sessionId:id,cwd,skipPerms:skip}) });
    const d = await r.json();
    showToast(d.ok ? 'Launched in new Terminal tab' : 'Launch failed');
  } catch (e) { showToast('Launch failed'); }
}

function showNewSession(event) {
  event.stopPropagation();
  document.getElementById('new-modal').classList.add('visible');
  const dirInput = document.getElementById('new-dir');
  if (!dirInput.value) dirInput.value = defaultHomeDir + '/Documents/';
  dirInput.focus();
  dirInput.setSelectionRange(dirInput.value.length, dirInput.value.length);
  browseDir(dirInput.value);
}

let cachedDir = '';
let cachedEntries = [];

async function browseDir(inputVal) {
  const lastSlash = inputVal.lastIndexOf('/');
  const parentDir = inputVal.substring(0, lastSlash + 1);
  const filter = inputVal.substring(lastSlash + 1).toLowerCase();

  if (parentDir !== cachedDir) {
    try {
      const r = await fetch('/api/ls?dir=' + encodeURIComponent(parentDir));
      const d = await r.json();
      cachedDir = parentDir;
      cachedEntries = d.ok ? d.entries : [];
    } catch (e) { cachedEntries = []; }
  }

  const filtered = filter
    ? cachedEntries.filter(e => e.toLowerCase().startsWith(filter))
    : cachedEntries;

  const browser = document.getElementById('dir-browser');
  if (!filtered.length) {
    browser.innerHTML = '<div class="dir-entry dir-up" onclick="goUpDir()"><span class="dir-icon">..</span> up</div>'
      + (filter ? '<div class="dir-entry" style="color:var(--text-input-placeholder);cursor:default">no matches</div>' : '<div class="dir-entry" style="color:var(--text-input-placeholder);cursor:default">no subdirectories</div>');
    return;
  }
  browser.innerHTML = '<div class="dir-entry dir-up" onclick="goUpDir()"><span class="dir-icon">..</span> up</div>'
    + filtered.map(e => `<div class="dir-entry" onclick="selectDir('${escapeHtml(parentDir + e)}')"><span class="dir-icon">+</span> ${escapeHtml(e)}</div>`).join('');
}

function selectDir(dir) {
  const input = document.getElementById('new-dir');
  input.value = dir + '/';
  input.focus();
  browseDir(dir);
}

function goUpDir() {
  const input = document.getElementById('new-dir');
  let dir = input.value.replace(/\/+$/, '');
  const parent = dir.substring(0, dir.lastIndexOf('/'));
  if (parent) {
    input.value = parent + '/';
    input.focus();
    browseDir(parent);
  }
}

async function createFolder() {
  const dirInput = document.getElementById('new-dir');
  const nameInput = document.getElementById('new-folder-name');
  const name = nameInput.value.trim();
  if (!name) { showToast('Enter a folder name'); return; }
  let parent = dirInput.value.replace(/\/+$/, '');
  const newPath = parent + '/' + name;
  try {
    const r = await fetch('/api/mkdir', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ path: newPath }) });
    const d = await r.json();
    if (d.ok) {
      nameInput.value = '';
      selectDir(newPath);
      showToast('Created ' + name);
    } else {
      showToast('Failed: ' + (d.error || 'unknown'));
    }
  } catch (e) { showToast('Failed to create folder'); }
}

let browseTimeout;
document.addEventListener('DOMContentLoaded', () => {
  const dirInput = document.getElementById('new-dir');
  if (dirInput) {
    dirInput.addEventListener('input', () => {
      clearTimeout(browseTimeout);
      browseTimeout = setTimeout(() => browseDir(dirInput.value), 300);
    });
  }
});

function closeNewSession() {
  document.getElementById('new-modal').classList.remove('visible');
  document.getElementById('new-dir').value = '';
  document.getElementById('new-prompt').value = '';
  document.getElementById('new-skip-perms').checked = false;
}

async function launchNewSession() {
  const dir = document.getElementById('new-dir').value.trim();
  if (!dir) { showToast('Enter a directory'); return; }
  const prompt = document.getElementById('new-prompt').value.trim();
  const skip = document.getElementById('new-skip-perms').checked;
  try {
    const r = await fetch('/api/new', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dir, prompt, skipPerms: skip }),
    });
    const d = await r.json();
    if (d.ok) {
      closeNewSession();
      showToast('Launched new Claude session');
    } else {
      showToast('Launch failed: ' + (d.error || 'unknown'));
    }
  } catch (e) { showToast('Launch failed'); }
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('visible');
  setTimeout(() => t.classList.remove('visible'), 3000);
}


// --- Recent section toggle ---
function toggleRecent() {
  const wrap = document.getElementById('recent-wrap');
  const arrow = document.getElementById('recent-arrow');
  wrap.classList.toggle('collapsed');
  arrow.classList.toggle('collapsed');
}

// --- Pixel dialog ---
let pixelDialogPid = null;
let pixelDialogTty = null;
let pixelDialogCwd = null;

function openPixelDialog(pid, tty) {
  pixelDialogPid = pid;
  pixelDialogTty = tty;
  const all = getMergedLive();
  const session = all.find(s => s.pid === pid);
  pixelDialogCwd = session?.cwd || '';
  if (!session) return;

  document.getElementById('pxd-project').textContent = getDisplayName(session.cwd, session.projectName);
  const statusEl = document.getElementById('pxd-status');
  statusEl.textContent = getStatusLabel(session.status);
  statusEl.style.color = getStatusColor(session.status);

  const hist = document.getElementById('pxd-history');
  hist.innerHTML = (session.messages || []).map(m => `
    <div class="msg-bubble ${m.role}">
      <span class="msg-role">${m.role === 'assistant' ? 'Claude' : 'You'}</span>
      <div class="msg-text">${escapeHtml(m.text)}</div>
    </div>
  `).join('');
  hist.scrollTop = hist.scrollHeight;

  document.getElementById('pxd-input').value = '';
  document.getElementById('pixel-modal').classList.add('visible');
  setTimeout(() => document.getElementById('pxd-input').focus(), 100);
}

function closePixelDialog() {
  document.getElementById('pixel-modal').classList.remove('visible');
  pixelDialogPid = null;
  pixelDialogTty = null;
  pixelDialogCwd = null;
}

async function sendPixelMsg(event) {
  event.stopPropagation();
  const input = document.getElementById('pxd-input');
  const msg = input.value.trim();
  if (!msg || !pixelDialogTty) return;
  try {
    const res = await fetch('/api/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tty: pixelDialogTty, message: msg, cwd: pixelDialogCwd || '' }),
    });
    const data = await res.json();
    if (data.ok) {
      input.value = '';
      const sent = document.getElementById('pxd-sent');
      sent.textContent = 'sent to terminal!';
      sent.classList.add('visible');
      setTimeout(() => sent.classList.remove('visible'), 2500);
    } else {
      showToast('Failed to send: ' + (data.error || 'unknown'));
    }
  } catch (e) { showToast('Failed to send'); }
}

async function pixelOpenTerminal(event) {
  event.stopPropagation();
  if (!pixelDialogTty) return;
  try { await fetch('/api/focus?tty=' + encodeURIComponent(pixelDialogTty) + '&pid=' + encodeURIComponent(pixelDialogPid) + '&cwd=' + encodeURIComponent(pixelDialogCwd || '')); } catch (e) { /* ignore */ }
}

// --- Wake offline project ---
async function wakeProject(cwd, sessionId) {
  try {
    const r = await fetch('/api/launch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, cwd, skipPerms: true }),
    });
    const d = await r.json();
    showToast(d.ok ? 'Waking up session in new Terminal tab' : 'Launch failed');
  } catch (e) { showToast('Launch failed'); }
}

// --- View toggle ---
let currentView = localStorage.getItem('see-claude-view') || 'terminal';

function setView(view) {
  currentView = view;
  localStorage.setItem('see-claude-view', view);
  document.getElementById('live-section').style.display = view === 'terminal' ? 'block' : 'none';
  document.getElementById('pixel-view').classList.toggle('active', view === 'pixel');
  document.getElementById('vbtn-terminal').classList.toggle('active', view === 'terminal');
  document.getElementById('vbtn-pixel').classList.toggle('active', view === 'pixel');
  if (view === 'pixel' && lastData) renderPixel(getMergedLive());
}

setTimeout(() => { if (currentView === 'pixel') setView('pixel'); }, 0);

// --- Office environment ---
function getSkyColor() {
  const h = new Date().getHours();
  if (h >= 6 && h < 8) return 'linear-gradient(180deg, #2d1b4e 0%, #e8846b 50%, #f4c27f 100%)';
  if (h >= 8 && h < 12) return 'linear-gradient(180deg, #4a90d9 0%, #87ceeb 50%, #b8e0f0 100%)';
  if (h >= 12 && h < 17) return 'linear-gradient(180deg, #2d7dd2 0%, #87ceeb 100%)';
  if (h >= 17 && h < 20) return 'linear-gradient(180deg, #1a1a3e 0%, #d4556b 50%, #f4a742 100%)';
  if (h >= 20 && h < 22) return 'linear-gradient(180deg, #0a0a2e 0%, #1a1a4e 50%, #2d1b4e 100%)';
  return 'linear-gradient(180deg, #050510 0%, #0a0a2e 50%, #111133 100%)';
}

function updateOffice() {
  const sky = document.getElementById('office-sky');
  const clock = document.getElementById('office-clock');
  if (sky) sky.style.background = getSkyColor();
  if (clock) {
    const now = new Date();
    clock.textContent = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');
  }
}
updateOffice();
setInterval(updateOffice, 30000);

// --- Desktop notifications + Sound alerts ---
let prevStatuses = {};

function checkNotifications(sessions) {
  sessions.forEach(s => {
    const prev = prevStatuses[s.pid];
    if (prev && (prev === 'working' || prev === 'thinking') && s.status === 'idle') {
      // Desktop notification
      if (Notification.permission === 'granted') {
        new Notification('Claude finished', {
          body: s.projectName + ' is now idle',
          icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">\uD83D\uDDA5\uFE0F</text></svg>',
          silent: false,
        });
      }
      // Feature 4: Sound alert
      if (soundEnabled) {
        playChime();
      }
    }
    prevStatuses[s.pid] = s.status;
  });
}

if ('Notification' in window && Notification.permission === 'default') {
  setTimeout(() => {
    Notification.requestPermission();
  }, 3000);
}

// --- Pixel click with dblclick support ---
let pixelClickTimer = null;

function pixelClick(el, pid, tty, type, cwd, sessionId) {
  if (pixelClickTimer) { clearTimeout(pixelClickTimer); pixelClickTimer = null; return; }
  pixelClickTimer = setTimeout(() => {
    pixelClickTimer = null;
    if (type === 'live') openPixelDialog(pid, tty);
    else wakeProject(cwd, sessionId);
  }, 250);
}

document.addEventListener('dblclick', (e) => {
  const label = e.target.closest('.pixel-label');
  if (!label || !label.dataset.cwd) return;
  e.stopPropagation();
  if (pixelClickTimer) { clearTimeout(pixelClickTimer); pixelClickTimer = null; }
  renameProject(label.dataset.cwd, label.dataset.fallback, label);
});

// --- Custom project names ---
let customNames = JSON.parse(localStorage.getItem('see-claude-names') || '{}');

function getDisplayName(cwd, fallback) {
  return customNames[cwd] || fallback;
}

function renameProject(cwd, fallback, el) {
  const input = document.createElement('input');
  input.className = 'chat-input';
  input.value = customNames[cwd] || '';
  input.placeholder = fallback;
  input.style.cssText = 'width:100%;font-size:11px;padding:2px 6px;text-align:center;margin-top:8px';
  el.replaceWith(input);
  input.focus();
  input.select();
  const save = () => {
    const val = input.value.trim();
    if (val) customNames[cwd] = val;
    else delete customNames[cwd];
    localStorage.setItem('see-claude-names', JSON.stringify(customNames));
    const label = document.createElement('div');
    label.className = 'pixel-label';
    label.textContent = val || fallback;
    label.ondblclick = (e) => { e.stopPropagation(); renameProject(cwd, fallback, label); };
    input.replaceWith(label);
  };
  input.addEventListener('blur', save);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
    if (e.key === 'Escape') { input.value = ''; input.blur(); }
  });
  input.addEventListener('click', (e) => e.stopPropagation());
}

// --- Drag to reorder (pixel view) ---
let rosterOrder = JSON.parse(localStorage.getItem('see-claude-roster-order') || '[]');

function applyRosterOrder(items) {
  if (!rosterOrder.length) return items;
  const orderMap = {};
  rosterOrder.forEach((key, i) => { orderMap[key] = i; });
  return items.sort((a, b) => {
    const keyA = a.type === 'live' ? a.session.cwd : a.project.cwd;
    const keyB = b.type === 'live' ? b.session.cwd : b.project.cwd;
    const oA = orderMap[keyA] !== undefined ? orderMap[keyA] : 9999;
    const oB = orderMap[keyB] !== undefined ? orderMap[keyB] : 9999;
    if (oA !== oB) return oA - oB;
    if (a.type !== b.type) return a.type === 'live' ? -1 : 1;
    return 0;
  });
}

let dragSrcEl = null;

function initDrag(floor) {
  const stations = floor.querySelectorAll('.pixel-station');
  stations.forEach(el => {
    el.setAttribute('draggable', 'true');
    el.addEventListener('dragstart', (e) => {
      dragSrcEl = el;
      el.style.opacity = '0.4';
      e.dataTransfer.effectAllowed = 'move';
    });
    el.addEventListener('dragend', () => { el.style.opacity = ''; });
    el.addEventListener('dragover', (e) => {
      e.preventDefault(); e.dataTransfer.dropEffect = 'move';
      const rect = el.getBoundingClientRect();
      const mid = rect.left + rect.width / 2;
      if (e.clientX < mid) {
        el.style.borderLeft = '3px solid var(--drag-indicator)'; el.style.borderRight = '';
      } else {
        el.style.borderRight = '3px solid var(--drag-indicator)'; el.style.borderLeft = '';
      }
    });
    el.addEventListener('dragleave', () => { el.style.borderLeft = ''; el.style.borderRight = ''; });
    el.addEventListener('drop', (e) => {
      e.preventDefault();
      el.style.borderLeft = ''; el.style.borderRight = '';
      if (dragSrcEl !== el) {
        const parent = el.parentNode;
        const rect = el.getBoundingClientRect();
        const mid = rect.left + rect.width / 2;
        if (e.clientX < mid) parent.insertBefore(dragSrcEl, el);
        else parent.insertBefore(dragSrcEl, el.nextSibling);
        const newOrder = [...parent.querySelectorAll('.pixel-station')].map(s => s.dataset.cwd).filter(Boolean);
        rosterOrder = newOrder;
        localStorage.setItem('see-claude-roster-order', JSON.stringify(newOrder));
      }
    });
  });
}

// --- Pixel art renderer ---
const PX = 4;
let pixelAnimFrame = 0;
setInterval(() => { pixelAnimFrame++; }, 400);

const HAIR_COLORS = ['#6b4226','#2a1a0a','#d4a44a','#c24a2a','#8a2a4a','#f5f5dc','#1a1a2e','#ff6b35'];
const SKIN_COLORS = ['#f0c090','#d4a070','#8d5524','#c68642','#f1c27d','#e0ac69','#503335','#ffdbac'];
const SHIRT_COLORS = ['#5b8dd9','#d95b5b','#5bd98a','#d9b95b','#9b5bd9','#d95bba','#5bd9d9','#ff6b35'];
const PANTS_COLORS = ['#3b4a6b','#4a3b6b','#3b6b4a','#6b4a3b','#2d2d3d','#3d2d2d','#2d3d2d','#444'];
const HAIR_STYLES = ['short','spiky','long','ponytail','mohawk','bun','curly','buzzcut'];
const DESK_ITEMS = ['coffee','plant','cat','book','headphones','duck'];
const CHAIR_COLORS = ['#444','#6b2222','#22446b','#226b44','#6b4422','#4a2266'];

function hashPid(pid) {
  let h = 0;
  for (let i = 0; i < pid.length; i++) h = ((h << 5) - h + pid.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function getCharTraits(pid) {
  const h = hashPid(pid);
  return {
    hair: HAIR_COLORS[h % HAIR_COLORS.length],
    skin: SKIN_COLORS[(h >> 3) % SKIN_COLORS.length],
    shirt: SHIRT_COLORS[(h >> 6) % SHIRT_COLORS.length],
    pants: PANTS_COLORS[(h >> 9) % PANTS_COLORS.length],
    hairStyle: HAIR_STYLES[(h >> 12) % HAIR_STYLES.length],
    deskItem: DESK_ITEMS[(h >> 15) % DESK_ITEMS.length],
    chairColor: CHAIR_COLORS[(h >> 18) % CHAIR_COLORS.length],
  };
}

function drawPixelCharacter(canvas, status, frame, pid) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const tc = getThemeColors();
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, w, canvas.height);

  const p = PX;
  const cx = Math.floor(w / 2);
  const t = getCharTraits(pid || '0');

  const screenGlow = status === 'working' ? tc.screenGlowWorking : status === 'thinking' ? tc.screenGlowThinking : tc.screenGlowIdle;
  const desk = tc.desk;
  const deskDark = tc.deskDark;

  // DESK
  ctx.fillStyle = desk;
  ctx.fillRect(cx - 22*p, 26*p, 44*p, 3*p);
  ctx.fillStyle = deskDark;
  ctx.fillRect(cx - 22*p, 29*p, 44*p, p);
  ctx.fillRect(cx - 20*p, 30*p, 2*p, 8*p);
  ctx.fillRect(cx + 18*p, 30*p, 2*p, 8*p);

  // MONITOR
  ctx.fillStyle = tc.monitor;
  ctx.fillRect(cx - 8*p, 16*p, 16*p, 10*p);
  ctx.fillStyle = tc.monitorInner;
  ctx.fillRect(cx - 7*p, 17*p, 14*p, 8*p);
  ctx.fillStyle = screenGlow;
  ctx.fillRect(cx - 6*p, 18*p, 12*p, 6*p);

  ctx.fillStyle = status === 'working' ? tc.textLinesWorking : status === 'thinking' ? tc.textLinesThinking : tc.textLinesIdle;
  const lo = frame % 3;
  for (let i = 0; i < 3; i++) {
    ctx.fillRect(cx - 5*p, (19 + i*2)*p, ((i + lo) % 3 === 0 ? 8 : (i + lo) % 3 === 1 ? 6 : 10)*p, p);
  }

  ctx.fillStyle = tc.monitorStand;
  ctx.fillRect(cx - 2*p, 26*p, 4*p, p);
  ctx.fillRect(cx - p, 25*p, 2*p, p);

  // CHAIR
  ctx.fillStyle = t.chairColor;
  ctx.fillRect(cx + 14*p, 22*p, 6*p, 2*p);
  ctx.fillRect(cx + 18*p, 16*p, 2*p, 6*p);
  ctx.fillRect(cx + 15*p, 24*p, p, 6*p);
  ctx.fillRect(cx + 19*p, 24*p, p, 6*p);
  ctx.fillStyle = tc.chairLegColor;
  ctx.fillRect(cx + 14*p, 30*p, 2*p, p);
  ctx.fillRect(cx + 19*p, 30*p, 2*p, p);

  // CHARACTER
  const charX = cx + 12*p;
  const charY = 8*p;
  const bobY = status === 'working' ? (frame % 2 === 0 ? 0 : -p) : 0;

  // Head
  ctx.fillStyle = t.skin;
  ctx.fillRect(charX, charY + bobY, 4*p, 4*p);

  // Hair
  ctx.fillStyle = t.hair;
  if (t.hairStyle === 'short') {
    ctx.fillRect(charX - p, charY + bobY - p, 6*p, 2*p);
    ctx.fillRect(charX - p, charY + bobY, p, 2*p);
  } else if (t.hairStyle === 'spiky') {
    ctx.fillRect(charX - p, charY + bobY - p, 6*p, p);
    ctx.fillRect(charX, charY + bobY - 2*p, p, p);
    ctx.fillRect(charX + 2*p, charY + bobY - 2*p, p, p);
    ctx.fillRect(charX + 4*p, charY + bobY - 2*p, p, p);
    ctx.fillRect(charX - p, charY + bobY, p, p);
  } else if (t.hairStyle === 'long') {
    ctx.fillRect(charX - p, charY + bobY - p, 6*p, 2*p);
    ctx.fillRect(charX - 2*p, charY + bobY, p, 5*p);
    ctx.fillRect(charX + 4*p, charY + bobY, p, 5*p);
  } else if (t.hairStyle === 'ponytail') {
    ctx.fillRect(charX - p, charY + bobY - p, 6*p, 2*p);
    ctx.fillRect(charX + 4*p, charY + bobY + p, p, p);
    ctx.fillRect(charX + 5*p, charY + bobY + 2*p, p, 3*p);
  } else if (t.hairStyle === 'mohawk') {
    ctx.fillRect(charX + p, charY + bobY - 3*p, 2*p, 3*p);
    ctx.fillRect(charX, charY + bobY - p, 4*p, p);
  } else if (t.hairStyle === 'bun') {
    ctx.fillRect(charX - p, charY + bobY - p, 6*p, 2*p);
    ctx.fillRect(charX + p, charY + bobY - 3*p, 2*p, 2*p);
  } else if (t.hairStyle === 'curly') {
    ctx.fillRect(charX - 2*p, charY + bobY - p, 7*p, 2*p);
    ctx.fillRect(charX - 2*p, charY + bobY, p, 3*p);
    ctx.fillRect(charX + 4*p, charY + bobY, p, 3*p);
    ctx.fillRect(charX - 2*p, charY + bobY + 3*p, p, p);
  } else {
    ctx.fillRect(charX, charY + bobY - p, 4*p, p);
  }

  // Eyes
  ctx.fillStyle = tc.eyes;
  if (status === 'idle') {
    ctx.fillRect(charX + p, charY + bobY + p, p, p);
    ctx.fillRect(charX + 2*p, charY + bobY + p, p, p);
  } else {
    ctx.fillRect(charX, charY + bobY + p, p, p);
    ctx.fillRect(charX + 2*p, charY + bobY + p, p, p);
  }

  // Mouth
  ctx.fillStyle = tc.mouth;
  if (status === 'working') {
    ctx.fillRect(charX + p, charY + bobY + 3*p, p, p);
  }

  // Body
  ctx.fillStyle = t.shirt;
  ctx.fillRect(charX - p, charY + bobY + 4*p, 6*p, 5*p);

  // Arms
  if (status === 'working') {
    const armOff = frame % 2 === 0 ? 0 : -p;
    ctx.fillStyle = t.shirt;
    ctx.fillRect(charX - 3*p, charY + bobY + 5*p, 2*p, 4*p);
    ctx.fillRect(charX + 5*p, charY + bobY + 5*p, 2*p, 4*p);
    ctx.fillStyle = t.skin;
    ctx.fillRect(charX - 3*p + armOff, charY + bobY + 9*p, 2*p, p);
    ctx.fillRect(charX + 5*p - armOff, charY + bobY + 9*p, 2*p, p);
  } else if (status === 'thinking') {
    ctx.fillStyle = t.shirt;
    ctx.fillRect(charX - 3*p, charY + bobY + 5*p, 2*p, 3*p);
    ctx.fillRect(charX + 5*p, charY + bobY + 5*p, 2*p, 4*p);
    ctx.fillStyle = t.skin;
    ctx.fillRect(charX - 2*p, charY + bobY + 3*p, 2*p, p);
    ctx.fillRect(charX + 5*p, charY + bobY + 9*p, 2*p, p);
  } else {
    ctx.fillStyle = t.shirt;
    ctx.fillRect(charX - 2*p, charY + bobY + 5*p, 2*p, 4*p);
    ctx.fillRect(charX + 4*p, charY + bobY + 5*p, 2*p, 4*p);
    ctx.fillStyle = t.skin;
    ctx.fillRect(charX - 2*p, charY + bobY + 9*p, 2*p, p);
    ctx.fillRect(charX + 4*p, charY + bobY + 9*p, 2*p, p);
  }

  // Pants
  ctx.fillStyle = t.pants;
  ctx.fillRect(charX - p, charY + bobY + 9*p, 6*p, 3*p);
  ctx.fillRect(charX - 2*p, charY + bobY + 12*p, 3*p, p);
  ctx.fillRect(charX + 3*p, charY + bobY + 12*p, 3*p, p);

  // Thought bubble
  if (status === 'thinking') {
    const bx = charX - 12*p;
    const by = charY + bobY - 4*p;
    ctx.fillStyle = tc.thoughtBubble;
    ctx.fillRect(bx, by, 8*p, 4*p);
    ctx.fillRect(bx + p, by - p, 6*p, p);
    ctx.fillRect(bx + p, by + 4*p, 6*p, p);
    ctx.fillStyle = tc.thoughtText;
    const dotAnim = frame % 4;
    for (let i = 0; i < 3; i++) {
      ctx.fillStyle = i <= dotAnim ? tc.thoughtDotActive : tc.thoughtDotInactive;
      ctx.fillRect(bx + (1 + i*2)*p, by + p, p, p);
    }
    ctx.fillStyle = tc.thoughtBubble;
    ctx.fillRect(charX - 3*p, charY + bobY - p, 2*p, p);
    ctx.fillRect(charX - 5*p, charY + bobY - 2*p, p, p);
  }

  // Keyboard
  ctx.fillStyle = tc.keyboard;
  ctx.fillRect(cx - 4*p, 25*p, 8*p, 2*p);
  ctx.fillStyle = tc.keyboardKeys;
  for (let i = 0; i < 3; i++) ctx.fillRect(cx - 3*p + i*3*p, 25*p, 2*p, p);

  // Desk item
  const ix = cx - 17*p;
  const iy = 23*p;

  if (t.deskItem === 'coffee') {
    ctx.fillStyle = '#ddd';
    ctx.fillRect(ix, iy + p, 3*p, 3*p);
    ctx.fillRect(ix + 3*p, iy + 2*p, p, p);
    if (status !== 'idle' && frame % 3 < 2) {
      ctx.fillStyle = 'rgba(255,255,255,0.3)';
      ctx.fillRect(ix + p, iy - p + (frame % 2)*p, p, p);
      ctx.fillRect(ix + 2*p, iy - 2*p + (frame % 2)*p, p, p);
    }
  } else if (t.deskItem === 'plant') {
    ctx.fillStyle = '#8b4513';
    ctx.fillRect(ix, iy + 2*p, 3*p, 2*p);
    ctx.fillStyle = '#27a33f';
    ctx.fillRect(ix + p, iy, p, 2*p);
    ctx.fillRect(ix, iy - p, p, 2*p);
    ctx.fillRect(ix + 2*p, iy - p, p, 2*p);
  } else if (t.deskItem === 'cat') {
    ctx.fillStyle = '#ff9944';
    ctx.fillRect(ix, iy + p, 3*p, 2*p);
    ctx.fillRect(ix + 3*p, iy, 2*p, 2*p);
    ctx.fillRect(ix + 3*p, iy - p, p, p);
    ctx.fillRect(ix + 4*p, iy - p, p, p);
    ctx.fillStyle = tc.eyes;
    ctx.fillRect(ix + 3*p, iy + p, p, p);
    ctx.fillStyle = '#ff9944';
    ctx.fillRect(ix - p, iy + (frame % 2)*p, p, 2*p);
  } else if (t.deskItem === 'book') {
    ctx.fillStyle = '#cc3333';
    ctx.fillRect(ix, iy + p, 3*p, 3*p);
    ctx.fillStyle = '#fff';
    ctx.fillRect(ix + p, iy + 2*p, p, p);
  } else if (t.deskItem === 'headphones') {
    ctx.fillStyle = tc.monitorStand;
    ctx.fillRect(ix, iy + 2*p, p, 2*p);
    ctx.fillRect(ix + 3*p, iy + 2*p, p, 2*p);
    ctx.fillRect(ix, iy + p, 4*p, p);
    ctx.fillStyle = '#666';
    ctx.fillRect(ix - p, iy + 2*p, 2*p, p);
    ctx.fillRect(ix + 3*p, iy + 2*p, 2*p, p);
  } else if (t.deskItem === 'duck') {
    ctx.fillStyle = '#ffd700';
    ctx.fillRect(ix, iy + p, 3*p, 2*p);
    ctx.fillRect(ix + 2*p, iy, 2*p, 2*p);
    ctx.fillStyle = '#ff8c00';
    ctx.fillRect(ix + 4*p, iy + p, p, p);
  }
}

function drawSleepingCharacter(canvas, frame, dirKey) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const tc = getThemeColors();
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, w, canvas.height);

  const p = PX;
  const cx = Math.floor(w / 2);
  const t = getCharTraits(dirKey || '0');

  const desk = tc.deskSleep;
  const deskDark = tc.deskSleepDark;

  ctx.fillStyle = desk;
  ctx.fillRect(cx - 22*p, 26*p, 44*p, 3*p);
  ctx.fillStyle = deskDark;
  ctx.fillRect(cx - 22*p, 29*p, 44*p, p);
  ctx.fillRect(cx - 20*p, 30*p, 2*p, 8*p);
  ctx.fillRect(cx + 18*p, 30*p, 2*p, 8*p);

  ctx.fillStyle = tc.monitorSleep;
  ctx.fillRect(cx - 8*p, 16*p, 16*p, 10*p);
  ctx.fillStyle = tc.monitorSleepInner;
  ctx.fillRect(cx - 7*p, 17*p, 14*p, 8*p);
  ctx.fillStyle = tc.monitorSleepDot;
  ctx.fillRect(cx, 20*p, p, p);
  ctx.fillStyle = tc.monitorSleep;
  ctx.fillRect(cx - 2*p, 26*p, 4*p, p);
  ctx.fillRect(cx - p, 25*p, 2*p, p);

  ctx.fillStyle = tc.chairSleepColor;
  ctx.fillRect(cx + 14*p, 22*p, 6*p, 2*p);
  ctx.fillRect(cx + 18*p, 16*p, 2*p, 6*p);
  ctx.fillRect(cx + 15*p, 24*p, p, 6*p);
  ctx.fillRect(cx + 19*p, 24*p, p, 6*p);
  ctx.fillStyle = tc.chairSleepLeg;
  ctx.fillRect(cx + 14*p, 30*p, 2*p, p);
  ctx.fillRect(cx + 19*p, 30*p, 2*p, p);

  const charX = cx + 4*p;
  const charY = 22*p;

  ctx.fillStyle = t.shirt;
  ctx.globalAlpha = 0.6;
  ctx.fillRect(charX, charY - 4*p, 6*p, 5*p);
  ctx.fillRect(charX - 2*p, charY - 2*p, 2*p, 3*p);
  ctx.fillRect(charX + 6*p, charY - 2*p, 2*p, 3*p);
  ctx.fillStyle = t.skin;
  ctx.fillRect(charX - 3*p, charY, 3*p, p);
  ctx.fillRect(charX + 6*p, charY, 3*p, p);
  ctx.fillStyle = t.skin;
  ctx.fillRect(charX + p, charY - 6*p, 4*p, 3*p);
  ctx.fillStyle = t.hair;
  ctx.fillRect(charX, charY - 7*p, 6*p, 2*p);

  ctx.fillStyle = tc.zzzColor;
  const zOff = frame % 3;
  ctx.fillRect(charX + 8*p, charY - (8 + zOff)*p, 2*p, p);
  if (zOff > 0) ctx.fillRect(charX + 10*p, charY - (10 + zOff)*p, 3*p, p);
  if (zOff > 1) ctx.fillRect(charX + 13*p, charY - (12 + zOff)*p, 3*p, p);

  ctx.fillStyle = t.pants;
  ctx.fillRect(charX, charY + p, 3*p, 4*p);
  ctx.fillRect(charX + 3*p, charY + p, 3*p, 4*p);

  ctx.globalAlpha = 1.0;

  ctx.fillStyle = tc.monitorSleep;
  ctx.fillRect(cx - 4*p, 25*p, 8*p, 2*p);
}

function renderPixel(sessions) {
  const floor = document.getElementById('pixel-floor');
  if (!floor) return;
  document.getElementById('count').textContent = sessions.filter(s => !s._machine || s._machine === 'local').length || sessions.length;

  const filtered = sessions.filter(matchesSearch);
  const roster = lastData?.roster || [];
  const liveByCwd = {};
  filtered.forEach(s => { liveByCwd[s.cwd] = s; });

  const items = [];
  const shownCwds = new Set();

  filtered.forEach(s => {
    items.push({ type: 'live', session: s });
    shownCwds.add(s.cwd);
  });

  let offlineCount = 0;
  roster.forEach(r => {
    if (!shownCwds.has(r.cwd) && offlineCount < 12) {
      items.push({ type: 'offline', project: r });
      shownCwds.add(r.cwd);
      offlineCount++;
    }
  });

  const ordered = applyRosterOrder(items);

  floor.innerHTML = ordered.map((item) => {
    if (item.type === 'live') {
      const s = item.session;
      const isRemote = s._machine && s._machine !== 'local';
      const realPid = isRemote ? s.pid.split(':').slice(1).join(':') : s.pid;
      const realTty = isRemote ? s.tty.split(':').slice(1).join(':') : s.tty;
      return `
        <div class="pixel-station" data-cwd="${escapeHtml(s.cwd)}" onclick="pixelClick(this, '${s.pid}', '${s.tty}', 'live')">
          <canvas id="pxc-${s.pid}" width="200" height="160" style="image-rendering:pixelated"></canvas>
          <div class="pixel-label" data-cwd="${escapeHtml(s.cwd)}" data-fallback="${escapeHtml(s.projectName)}">${escapeHtml(getDisplayName(s.cwd, s.projectName))}${machineBadgeHtml(s)}</div>
          <div class="pixel-status" style="color:${getStatusColor(s.status)}">${getStatusLabel(s.status)}</div>
          ${!isRemote ? `<button class="quick-terminal" onclick="event.stopPropagation();openTerminal('${realTty}','${s.pid}','${escapeHtml(s.cwd)}',event)" style="margin-top:4px">&gt;_ terminal</button>` : ''}
        </div>
      `;
    } else {
      const r = item.project;
      return `
        <div class="pixel-station offline" data-cwd="${escapeHtml(r.cwd)}" onclick="pixelClick(this, null, null, 'offline', '${escapeHtml(r.cwd)}', '${escapeHtml(r.latestSession)}')">
          <canvas id="pxr-${r.dirKey}" width="200" height="160" style="image-rendering:pixelated"></canvas>
          <div class="pixel-label" data-cwd="${escapeHtml(r.cwd)}" data-fallback="${escapeHtml(r.projectName)}">${escapeHtml(getDisplayName(r.cwd, r.projectName))}</div>
          <div class="pixel-status" style="color:var(--text-section)">offline</div>
          <div class="pixel-last-active">${r.lastModifiedStr}</div>
        </div>
      `;
    }
  }).join('');

  initDrag(floor);

  filtered.forEach(s => {
    const canvas = document.getElementById('pxc-' + s.pid);
    if (canvas) drawPixelCharacter(canvas, s.status, pixelAnimFrame, s.pid);
  });

  roster.forEach(r => {
    if (!liveByCwd[r.cwd]) {
      const canvas = document.getElementById('pxr-' + r.dirKey);
      if (canvas) drawSleepingCharacter(canvas, pixelAnimFrame, r.dirKey);
    }
  });
}

// Animate pixel view
setInterval(() => {
  if (currentView === 'pixel' && lastData) {
    const all = getMergedLive();
    const liveCwds = new Set(all.map(s => s.cwd));
    all.forEach(s => {
      const canvas = document.getElementById('pxc-' + s.pid);
      if (canvas) drawPixelCharacter(canvas, s.status, pixelAnimFrame, s.pid);
    });
    (lastData.roster || []).forEach(r => {
      if (!liveCwds.has(r.cwd)) {
        const canvas = document.getElementById('pxr-' + r.dirKey);
        if (canvas) drawSleepingCharacter(canvas, pixelAnimFrame, r.dirKey);
      }
    });
  }
}, 400);

// --- History dialog ---
let historySession = null;

async function openHistoryDialog(cwd, projectName, tty, pid, event) {
  if (event) event.stopPropagation();

  historySession = { cwd, projectName, tty, pid };
  document.getElementById('hd-project').textContent = projectName;

  const statusEl = document.getElementById('hd-meta');
  const all = getMergedLive();
  const session = all.find(s => s.pid === pid);
  if (session) {
    statusEl.textContent = getStatusLabel(session.status);
    statusEl.style.color = getStatusColor(session.status);
  } else {
    statusEl.textContent = '';
  }

  document.getElementById('hd-history').innerHTML = '<div class="hd-loading">Loading...</div>';
  document.getElementById('hd-input').value = '';
  document.getElementById('history-modal').classList.add('visible');

  try {
    const r = await fetch('/api/history?cwd=' + encodeURIComponent(cwd));
    const data = await r.json();
    const hist = document.getElementById('hd-history');
    if (data.ok && data.messages.length > 0) {
      hist.innerHTML = data.messages.map(m => `
        <div class="msg-bubble ${m.role}">
          <span class="msg-role">${m.role === 'assistant' ? 'Claude' : 'You'}</span>
          <div class="msg-text">${escapeHtml(m.text)}</div>
        </div>
      `).join('');
      hist.scrollTop = hist.scrollHeight;
    } else {
      hist.innerHTML = '<div class="hd-loading">No messages found</div>';
    }
  } catch (e) {
    document.getElementById('hd-history').innerHTML = '<div class="hd-loading">Failed to load history</div>';
  }

  setTimeout(() => document.getElementById('hd-input').focus(), 100);
}

let historyRefreshPending = false;

async function refreshHistoryDialog(merged) {
  if (!historySession || historyRefreshPending) return;
  // Don't refresh while user is typing
  if (document.activeElement?.id === 'hd-input' && document.getElementById('hd-input').value) return;

  // Update status from live data
  const session = merged.find(s => s.pid === historySession.pid);
  const statusEl = document.getElementById('hd-meta');
  if (session) {
    statusEl.textContent = getStatusLabel(session.status);
    statusEl.style.color = getStatusColor(session.status);
  }

  // Re-fetch full history
  historyRefreshPending = true;
  try {
    const r = await fetch('/api/history?cwd=' + encodeURIComponent(historySession.cwd));
    const data = await r.json();
    if (!historySession) return; // dialog was closed during fetch
    const hist = document.getElementById('hd-history');
    if (data.ok && data.messages.length > 0) {
      const wasAtBottom = hist.scrollTop + hist.clientHeight >= hist.scrollHeight - 30;
      hist.innerHTML = data.messages.map(m => `
        <div class="msg-bubble ${m.role}">
          <span class="msg-role">${m.role === 'assistant' ? 'Claude' : 'You'}</span>
          <div class="msg-text">${escapeHtml(m.text)}</div>
        </div>
      `).join('');
      if (wasAtBottom) hist.scrollTop = hist.scrollHeight;
    }
  } catch (e) { /* ignore refresh errors */ }
  finally { historyRefreshPending = false; }
}

function closeHistoryDialog() {
  document.getElementById('history-modal').classList.remove('visible');
  historySession = null;
}

async function openHistoryTerminal(event) {
  event.stopPropagation();
  if (!historySession || !historySession.tty) return;
  try { await fetch('/api/focus?tty=' + encodeURIComponent(historySession.tty) + '&pid=' + encodeURIComponent(historySession.pid) + '&cwd=' + encodeURIComponent(historySession.cwd || '')); } catch (e) { /* ignore */ }
}

async function sendHistoryMsg(event) {
  event.stopPropagation();
  if (!historySession || !historySession.tty) return;
  const input = document.getElementById('hd-input');
  const msg = input.value.trim();
  if (!msg) return;
  try {
    const res = await fetch('/api/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tty: historySession.tty, message: msg, cwd: historySession.cwd || '' }),
    });
    const data = await res.json();
    if (data.ok) {
      input.value = '';
      const sent = document.getElementById('hd-sent');
      sent.textContent = 'sent to terminal!';
      sent.classList.add('visible');
      setTimeout(() => sent.classList.remove('visible'), 2500);
    } else {
      showToast('Failed to send: ' + (data.error || 'unknown'));
    }
  } catch (e) { showToast('Failed to send'); }
}

// --- SSE ---
let lastData = null;

function connectSSE() {
  const src = new EventSource('/api/stream');
  src.onmessage = (e) => {
    try {
      lastData = JSON.parse(e.data);
      if (lastData.homeDir) defaultHomeDir = lastData.homeDir;

      // Feature 3: record resource history
      recordResourceHistory(lastData.live);

      const merged = getMergedLive();
      const inputFocused = expandedPid && document.activeElement?.id === 'input-' + expandedPid;
      const pixelDialogOpen = !!pixelDialogPid;
      if (!inputFocused && !pixelDialogOpen) {
        if (currentView === 'terminal') renderLive(merged);
        else renderPixel(merged);
      }
      if (pixelDialogOpen) {
        const session = merged.find(s => s.pid === pixelDialogPid);
        if (session) {
          const statusEl = document.getElementById('pxd-status');
          statusEl.textContent = getStatusLabel(session.status);
          statusEl.style.color = getStatusColor(session.status);
          const hist = document.getElementById('pxd-history');
          hist.innerHTML = (session.messages || []).map(m => `
            <div class="msg-bubble ${m.role}">
              <span class="msg-role">${m.role === 'assistant' ? 'Claude' : 'You'}</span>
              <div class="msg-text">${escapeHtml(m.text)}</div>
            </div>
          `).join('');
          hist.scrollTop = hist.scrollHeight;
        } else {
          closePixelDialog();
        }
      }
      if (historySession) {
        refreshHistoryDialog(merged);
      }
      renderRecent(getMergedRecent());
      checkNotifications(merged);
    } catch (e) { /* ignore parse errors */ }
  };
  src.onerror = () => { src.close(); setTimeout(connectSSE, 3000); };
}

fetch('/api/sessions').then(r => r.json()).then(data => {
  lastData = data;
  if (data.homeDir) defaultHomeDir = data.homeDir;
  recordResourceHistory(data.live);
  const merged = getMergedLive();
  if (currentView === 'terminal') renderLive(merged);
  else renderPixel(merged);
  renderRecent(getMergedRecent());
  connectSSE();
  fetchRemoteConfig();
}).catch(() => {
  connectSSE();
  fetchRemoteConfig();
});
