// Componentes comunes de los mockups: encabezado, barras de navegacion, mapa, graficos e iconos.
(function () {
  const svg = (name, cls = 'ic') => `<svg class="${cls}" viewBox="0 0 24 24">${(window.ICONS[name] || '')}</svg>`;
  const NAV = {
    passenger: [['search','search','Buscar'],['myTrips','calendar-check','Mis viajes'],['messages','message-circle','Mensajes'],['notifications','bell','Avisos'],['profile','circle-user','Perfil']],
    driver: [['home','house','Inicio'],['publish','square-plus','Publicar'],['myTrips','car','Mis viajes'],['messages','message-circle','Mensajes'],['profile','circle-user','Perfil']],
  };
  const DESK = [['dashboard','layout-dashboard','Panel'],['approvals','shield-check','Aprobaciones'],['users','users','Usuarios'],['trips','route','Viajes'],['emergencies','siren','Emergencias'],['moderation','message-square-warning','Moderación']];
  // Menu lateral de escritorio de pasajero y conductor (nombres completos, como en la app).
  const SIDE = {
    passenger: [['search','search','Buscar'],['myTrips','calendar-check','Mis viajes'],['messages','message-circle','Mensajes'],['notifications','bell','Notificaciones'],['profile','circle-user','Perfil']],
    driver: [['home','house','Inicio'],['publish','square-plus','Publicar'],['myTrips','car','Mis viajes'],['messages','message-circle','Mensajes'],['profile','circle-user','Perfil']],
  };
  const SETTING_TABS = ['Parámetros','Semestres','Lugares','Pico y placa','Legal','Administradores','Auditoría'];

  // Encabezado de cada pantalla.
  document.querySelectorAll('.frame').forEach((f) => {
    const h = document.createElement('div');
    h.className = 'fhead';
    h.innerHTML = `<div class="fnum">CARPOOL UP · MOCKUP ${f.dataset.n}</div><div class="ftitle">${f.dataset.t}</div><div class="fsub">${f.dataset.s}</div>`;
    if (f.classList.contains('d')) h.innerHTML = `<div class="fnum">MOCKUP ${f.dataset.n}${document.body.dataset.variant ? ' · ' + document.body.dataset.variant : ''}</div><div class="ftitle">${f.dataset.t}</div><div class="fsub">${f.dataset.s}</div>`;
    f.prepend(h);
  });

  document.querySelectorAll('[data-c="topbar"]').forEach((el) => {
    const n = el.dataset.badge;
    el.className = 'topbar';
    el.innerHTML = `<div class="brand"><div class="logo">${svg('car')}</div>Carpool UP</div><div class="roundbtn">${svg('bell')}${n ? `<span class="badge">${n}</span>` : ''}</div>`;
  });

  document.querySelectorAll('[data-c="tabbar"]').forEach((el) => {
    el.className = 'tabbar';
    el.innerHTML = NAV[el.dataset.role].map(([k, ic, label]) =>
      `<div class="tab ${k === el.dataset.active ? 'on' : ''}">${svg(ic)}<span>${label}</span>${k === 'messages' && el.dataset.badge ? '<span class="badge">2</span>' : ''}${k === 'notifications' && el.dataset.badge ? `<span class="badge">${el.dataset.badge}</span>` : ''}</div>`).join('');
  });

  document.querySelectorAll('.desk').forEach((el) => {
    const items = SIDE[el.dataset.role] || DESK.concat(el.dataset.role === 'superadmin' ? [['settings','settings','Configuración']] : []);
    const side = document.createElement('aside');
    side.className = 'side';
    side.innerHTML = `<div class="brand" style="padding:4px 8px 18px"><div class="logo">${svg('car')}</div>Carpool UP</div>` +
      items.map(([k, ic, label]) => `<div class="nav ${k === el.dataset.active ? 'on' : ''}">${svg(ic)}<span class="grow">${label}</span>${(k === 'emergencies' || k === 'notifications' || k === 'messages') && el.dataset[k] ? `<span class="badge" style="position:static">${el.dataset[k]}</span>` : ''}${k === 'emergencies' && el.dataset.badge ? '<span class="badge" style="position:static">1</span>' : ''}</div>`).join('') +
      `<div class="nav bottom muted">${svg('panel-left-close')}Contraer menú</div>`;
    el.prepend(side);
    const main = el.querySelector('.dmain');
    const top = document.createElement('div');
    top.className = 'dtop';
    const bell = el.dataset.bell ?? '2';
    top.innerHTML = `<div class="roundbtn">${svg('bell')}${bell !== '0' ? `<span class="badge">${bell}</span>` : ''}</div><div class="input" style="height:38px;border-radius:19px;width:150px">${svg('languages')}<span class="grow">Español</span>${svg('chevron-down')}</div><div class="roundbtn">${svg('monitor')}</div>`;
    main.prepend(top);
  });

  document.querySelectorAll('[data-c="settingtabs"]').forEach((el) => {
    el.innerHTML = SETTING_TABS.map((t, i) => `<span class="${String(i) === el.dataset.active ? 'on' : ''}">${t}</span>`).join('');
  });

  document.querySelectorAll('[data-c="bars"]').forEach((el) => {
    const v = el.dataset.v.split(',').map(Number); const max = Math.max(...v);
    el.innerHTML = v.map((x) => `<b class="${x === max ? 'hi' : ''}" style="height:${Math.max(2, (x / max) * 100)}%"></b>`).join('');
  });

  // Mapa esquematico: manzanas, calles, la ruta en el color de acento y los marcadores.
  document.querySelectorAll('[data-c="map"]').forEach((el) => {
    el.classList.add('map');
    const h = Number(el.dataset.h || 200);
    el.style.height = h + 'px';
    // El dibujo usa el ancho real del recuadro para que la ruta y los marcadores no se recorten.
    const w = Math.round(el.getBoundingClientRect().width) || 360, k = w / 360;
    const route = [[38, h - 30], [90, h - 46], [130, h * 0.62], [170, h * 0.52], [215, h * 0.46], [255, h * 0.34], [300, h * 0.22], [328, 38]].map(([x, y]) => [x * k, y]);
    const at = (t) => { const seg = (route.length - 1) * t, i = Math.min(Math.floor(seg), route.length - 2), f = seg - i;
      return [route[i][0] + (route[i + 1][0] - route[i][0]) * f, route[i][1] + (route[i + 1][1] - route[i][1]) * f]; };
    let s = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid slice"><rect width="${w}" height="${h}" fill="#eceef1"/>`;
    for (let x = -40; x < w + 40; x += 46) s += `<line x1="${x}" y1="0" x2="${x + 70}" y2="${h}" stroke="#fff" stroke-width="7"/>`;
    for (let y = 18; y < h; y += 42) s += `<line x1="0" y1="${y}" x2="${w}" y2="${y - 22}" stroke="#fff" stroke-width="6"/>`;
    s += `<path d="M0 ${h * 0.8} C 80 ${h * 0.7}, 140 ${h * 0.95}, ${w} ${h * 0.75}" stroke="#d3d7dd" stroke-width="10" fill="none"/>`;
    s += `<rect x="${250 * k}" y="${h * 0.55}" width="70" height="40" rx="6" fill="#dfe3e8"/><rect x="${40 * k}" y="20" width="60" height="34" rx="6" fill="#dfe3e8"/>`;
    s += `<polyline points="${route.map((p) => p.join(',')).join(' ')}" fill="none" stroke="#fff" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"/>`;
    s += `<polyline points="${route.map((p) => p.join(',')).join(' ')}" fill="none" stroke="#1e5aa8" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"/>`;
    const [ox, oy] = route[0], [dx, dy] = route[route.length - 1];
    s += `<circle cx="${ox}" cy="${oy}" r="8" fill="#fff" stroke="#22272e" stroke-width="3"/>`;
    if (el.hasAttribute('data-stop')) { const [sx, sy] = at(0.4); s += `<circle cx="${sx}" cy="${sy}" r="6" fill="#fff" stroke="#6b7280" stroke-width="3"/>`; }
    if (el.hasAttribute('data-pickup')) { const [px, py] = at(0.4); s += `<g transform="translate(${px - 11},${py - 32})"><path d="M11 0a11 11 0 0 1 11 11c0 8-11 19-11 19S0 19 0 11A11 11 0 0 1 11 0z" fill="#1e5aa8"/><circle cx="11" cy="11" r="4" fill="#fff"/></g>`; }
    s += `<g transform="translate(${dx - 4},${dy - 24})"><line x1="4" y1="0" x2="4" y2="26" stroke="#22272e" stroke-width="3"/><path d="M4 1h16l-4 6 4 6H4z" fill="#22272e"/></g>`;
    if (el.dataset.car) { const [cx, cy] = at(Number(el.dataset.car));
      s += `<circle cx="${cx}" cy="${cy}" r="17" fill="#1e5aa8" opacity=".18"/><circle cx="${cx}" cy="${cy}" r="12" fill="#1e5aa8" stroke="#fff" stroke-width="3"/>`;
      s += `<g transform="translate(${cx - 7},${cy - 7}) scale(.58)" stroke="#fff" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">${window.ICONS.car}</g>`; }
    if (el.hasAttribute('data-alert')) { const [ax, ay] = at(0.6); s += `<circle cx="${ax}" cy="${ay}" r="26" fill="none" stroke="#22272e" stroke-dasharray="4 4" stroke-width="2"/>`; }
    s += `<rect x="${w - 34}" y="${h - 64}" width="24" height="48" rx="6" fill="#fff" stroke="#cfd4dc"/><text x="${w - 22}" y="${h - 45}" font-size="16" text-anchor="middle" fill="#22272e">+</text><text x="${w - 22}" y="${h - 23}" font-size="16" text-anchor="middle" fill="#22272e">−</text>`;
    s += `<text x="8" y="${h - 8}" font-size="9" fill="#6b7280">© OpenStreetMap</text></svg>`;
    el.innerHTML = s;
  });

  document.querySelectorAll('i[data-i]').forEach((el) => {
    const t = document.createElement('span');
    t.innerHTML = svg(el.dataset.i, 'ic ' + (el.className || ''));
    const node = t.firstChild;
    if (el.getAttribute('style')) node.setAttribute('style', el.getAttribute('style').replace('--s:', 'width:') + ';' + el.getAttribute('style').replace('--s:', 'height:'));
    el.replaceWith(node);
  });
  document.body.dataset.ready = '1';
})();
