(function () {
  'use strict';

  var _modeFlag = document.getElementById('csModeFlag');
  var MODE = (_modeFlag && _modeFlag.dataset && _modeFlag.dataset.mode) || 'challan';
  var IS_CHALLAN = MODE !== 'audit';
  var IS_PREVIEW = true;
  var IS_DJANGO = false;

  var SAMPLE = {
    authority_en: 'SAFE CITY TRAFFIC POLICE',
    authority_ur: 'سیف سٹی ٹریفک پولیس',
    tagline: 'SERVICE · SECURITY · SAFETY',
    tagline_ur: 'خدمت · حفاظت · سیکورٹی',
    ticket_no: '20990001',
    plate: 'LEA-1234',
    psid: '209900011',
    issue: '05-Nov-2026',
    issue_time: '14:25',
    violation: 'Wrong Way',
    fine: '2000',
    fine_words: 'Two Thousand Rupees Only',
    owner: 'Ahmed Khan',
    cnic: '35202-1234567-1',
    address: 'House 12, Street 4, Gulberg III, Lahore',
    phone: '0300-1234567',
    vehicle_type: 'Car',
    make: '2023',
    color: 'White',
    chassis: 'CHS-99887766',
    location: 'Canal Road, Lahore',
    datetime: '2026-11-05 14:23:01',
    camera: 'CAM-001-FYP',
    moving: 'DOWN',
    legal: 'UP',
    conf: '0.93',
    due: '05-Dec-2026',
    due_days: '30',
    helpline: '15',
    website: 'safecity.gov.pk',
    officer: 'Omar Officer',
    designation: 'Traffic Officer',
    staff_id: 'PSC-2026-OFF-004',
    hash: 'ab12cd34ef56',
    track: 'TRK-1-LEA-0001',
    frames: [
      { n: 1, plate: 'LEA-1234', conf: '0.92', ocr: '0.86', ts: '14:23:01.108', complete: true },
      { n: 2, plate: 'LEA-1234', conf: '0.94', ocr: '0.89', ts: '14:23:01.241', complete: true },
      { n: 3, plate: 'LEA-1234', conf: '0.95', ocr: '0.91', ts: '14:23:01.374', complete: true }
    ],
    qr_placeholder: 'data:image/svg+xml;utf8,' + encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="84" height="84"><rect width="84" height="84" fill="#fff"/><g fill="#111">' +
      Array.from({ length: 49 }, function (_, i) {
        return ((i * 7 + (i % 5) * 3) % 3 === 0) ? '<rect x="' + (4 + (i % 7) * 11) + '" y="' + (4 + Math.floor(i / 7) * 11) + '" width="10" height="10"/>' : '';
      }).join('') + '</g></svg>'),
    plate_img: 'data:image/svg+xml;utf8,' + encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="220" height="70"><rect width="220" height="70" rx="6" fill="#f8fafc" stroke="#111" stroke-width="3"/><rect x="6" y="6" width="14" height="58" fill="#0b3a78"/><text x="50%" y="55%" font-family="Arial" font-size="34" font-weight="bold" text-anchor="middle" fill="#0b172a">LEA-1234</text></svg>'),
    cam_img: 'data:image/svg+xml;utf8,' + encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="270"><rect width="480" height="270" fill="#3a3d42"/><circle cx="240" cy="135" r="70" fill="#4b5563"/><rect x="150" y="90" width="180" height="90" rx="8" fill="#6b7280"/><rect x="0" y="0" width="480" height="20" fill="#111"/><text x="10" y="14" font-family="monospace" font-size="12" fill="#eee">CAM-001-FYP 2026-11-05 14:23:01</text><rect x="160" y="95" width="160" height="80" fill="none" stroke="#e22" stroke-width="2"/></svg>')
  };

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function attr(s) { return esc(s); }

  var STARTER_COMPOSITIONS = {
    standard_a4: ['header', 'meta_bar', 'vehicle_owner', 'violation', 'fine_payment', 'evidence', 'frame_table', 'instructions', 'signature', 'footer'],
    bilingual_a4: ['header', 'meta_bar', 'vehicle_owner', 'violation', 'evidence', 'fine_payment', 'instructions', 'signature', 'footer'],
    notice_classic_a4: ['header', 'meta_bar', 'vehicle_owner', 'violation', 'evidence', 'fine_payment', 'urdu_notice', 'signature', 'footer'],
    psca_urdu_a4: ['header', 'meta_bar', 'vehicle_owner', 'violation', 'evidence', 'frame_table', 'urdu_notice', 'po_copy', 'signature', 'footer'],
    government_grid_a4: ['header', 'meta_bar', 'vehicle_owner', 'violation', 'evidence', 'frame_table', 'instructions', 'signature', 'barcode', 'po_copy', 'footer']
  };

  var BLOCKS = {};

  function block(type, def) { BLOCKS[type] = def; def.type = type; }

  block('header', {
    label: 'Authority Header', icon: 'bi-heading', desc: 'Logos + EN/UR titles + tagline',
    props: { title_en: 'SAFE CITY TRAFFIC POLICE', title_ur: 'سیف سٹی ٹریفک پولیس', tagline: 'SERVICE · SECURITY · SAFETY', tagline_ur: 'خدمت · حفاظت · سیکورٹی', show_logos: true, show_urdu: true },
    schema: [
      { k: 'title_en', t: 'text', l: 'Title (English)' },
      { k: 'title_ur', t: 'text', l: 'Title (Urdu)' },
      { k: 'tagline', t: 'text', l: 'Tagline' },
      { k: 'tagline_ur', t: 'text', l: 'Tagline (Urdu)' },
      { k: 'show_logos', t: 'check', l: 'Show logo slots' },
      { k: 'show_urdu', t: 'check', l: 'Show Urdu column' }
    ],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      return '<div class="cst-hd" style="background:' + th.primary + '">' +
        (p.show_logos ? '<div class="cst-hd-logo"><span>LOGO</span></div>' : '') +
        '<div class="cst-hd-mid"><div class="cst-hd-t">' + v(esc(p.title_en), '{{ branding.authority_name_en }}') + '</div>' +
        '<div class="cst-hd-tag">' + v(esc(p.tagline), '{{ branding.tagline_en }}') + '</div></div>' +
        (p.show_urdu ? '<div class="cst-hd-ur"><div>' + v(esc(p.title_ur), '{{ branding.authority_name_ur }}') + '</div><div class="cst-hd-tag-ur">' + v(esc(p.tagline_ur), '{{ branding.tagline_ur }}') + '</div></div>' : '') +
        (p.show_logos ? '<div class="cst-hd-logo"><span>BADGE</span></div>' : '') +
        '</div>';
    }
  });

  block('meta_bar', {
    label: 'Challan Meta Bar', icon: 'bi-upc-scan', desc: 'Challan no · date · vehicle',
    props: { bg: '' },
    schema: [],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var bg = p.bg || th.primary;
      return '<div class="cst-bar" style="background:' + bg + '">' +
        '<span>Challan No: <b>' + v(SAMPLE.ticket_no, '{{ challan.ticket_no }}') + '</b></span>' +
        '<span>Issue: <b>' + v(SAMPLE.issue + ' ' + SAMPLE.issue_time, '{{ challan.issue_date|date:"d-M-Y" }} {{ challan.created_at|time:"H:i" }}') + '</b></span>' +
        '<span>Vehicle: <b>' + v(SAMPLE.plate, '{{ challan.plate_number }}') + '</b></span>' +
        '</div>';
    }
  });

  block('qr_box', {
    label: 'QR Payment Box', icon: 'bi-qr-code', desc: 'QR + PSID + scan caption',
    props: { caption: 'Scan to View / Pay' },
    schema: [{ k: 'caption', t: 'text', l: 'Caption' }],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var qr = pv ? SAMPLE.qr_placeholder : '';
      return '<div class="cst-qrbox"><div class="cst-qr">' + (pv ? '<img src="' + qr + '" alt="">' : '{% if qr_code_data_url %}<img src="{{ qr_code_data_url }}" alt="QR">{% endif %}') + '</div>' +
        '<div class="cst-qr-cap">' + v(esc(p.caption), esc(p.caption)) + '</div>' +
        '<div class="cst-qr-psid">PSID: ' + v(SAMPLE.psid, '{{ challan.psid }}') + '</div></div>';
    }
  });

  block('vehicle_owner', {
    label: 'Vehicle + Owner Panel', icon: 'bi-car-front', desc: 'Registration, owner, CNIC, address',
    props: { columns: '2', show_vehicle: true, show_owner: true },
    schema: [
      { k: 'columns', t: 'select', l: 'Columns', opts: [['1', 'Stacked'], ['2', 'Two columns']] },
      { k: 'show_vehicle', t: 'check', l: 'Vehicle section' },
      { k: 'show_owner', t: 'check', l: 'Owner section' }
    ],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      function veh() {
        return '<div class="cst-panel"><div class="cst-panel-h">Vehicle Information</div><div class="cst-kv">' +
          '<div class="cst-kv-r"><span>Registration No</span><b>' + v(SAMPLE.plate, '{{ challan.plate_number }}') + '</b></div>' +
          '<div class="cst-kv-r"><span>Type / Make</span><b>' + v(SAMPLE.vehicle_type + ' · ' + SAMPLE.make, '{{ challan.vehicle_type|default:"Car" }} · {{ challan.make_year|default:"—" }}') + '</b></div>' +
          '<div class="cst-kv-r"><span>Color</span><b>' + v(SAMPLE.color, '{{ challan.color|default:"—" }}') + '</b></div>' +
          '<div class="cst-kv-r"><span>Chassis No</span><b>' + v(SAMPLE.chassis, '{{ challan.chassis_no|default:"—" }}') + '</b></div>' +
          '</div></div>';
      }
      function own() {
        return '<div class="cst-panel"><div class="cst-panel-h">Owner Information</div><div class="cst-kv">' +
          '<div class="cst-kv-r"><span>Name</span><b>' + v(SAMPLE.owner, '{{ challan.owner_name|default:"Awaiting Excise Integration" }}') + '</b></div>' +
          '<div class="cst-kv-r"><span>CNIC</span><b>' + v(SAMPLE.cnic, '{{ challan.cnic|default:"Awaiting Excise Integration" }}') + '</b></div>' +
          '<div class="cst-kv-r"><span>Phone</span><b>' + v(SAMPLE.phone, '{{ challan.phone|default:"—" }}') + '</b></div>' +
          '<div class="cst-kv-r"><span>Address</span><b>' + v(SAMPLE.address, '{{ challan.address|default:"Awaiting Excise Integration" }}') + '</b></div>' +
          '</div></div>';
      }
      var inner = (p.show_vehicle ? veh() : '') + (p.show_owner ? own() : '');
      var cls = p.columns === '1' ? 'cst-cols cst-cols-1' : 'cst-cols cst-cols-2';
      return '<div class="' + cls + '">' + inner + '</div>';
    }
  });

  block('violation', {
    label: 'Violation Panel', icon: 'bi-exclamation-octagon', desc: 'Type, location, time, fine',
    props: { show_speed: false, show_qr: false },
    schema: [
      { k: 'show_speed', t: 'check', l: 'Show speed rows' },
      { k: 'show_qr', t: 'check', l: 'Inline QR box' }
    ],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var speed = p.show_speed ?
        '<div class="cst-kv-r"><span>Speed Limit</span><b>' + v('N/A', '{{ speed.allowed }}') + '</b></div>' +
        '<div class="cst-kv-r"><span>Detected Speed</span><b>' + v('N/A', '{{ speed.detected }}') + '</b></div>' : '';
      var qr = p.show_qr ? BLOCKS.qr_box.html({ caption: 'Scan to Pay' }, th, pv) : '';
      return '<div class="cst-cols cst-cols-2"><div class="cst-panel"><div class="cst-panel-h cst-panel-red">Violation Details</div><div class="cst-kv">' +
        '<div class="cst-kv-r"><span>Violation Type</span><b class="cst-red">' + v(SAMPLE.violation.toUpperCase(), '{{ challan.get_violation_type_display|upper }}') + '</b></div>' +
        '<div class="cst-kv-r"><span>Location</span><b>' + v(SAMPLE.location, '{{ challan.location|default:"—" }}') + '</b></div>' +
        '<div class="cst-kv-r"><span>Date &amp; Time</span><b>' + v(SAMPLE.datetime, '{{ camera_meta.timestamp }}') + '</b></div>' +
        '<div class="cst-kv-r"><span>Moving / Legal Dir</span><b>' + v(SAMPLE.moving + ' / ' + SAMPLE.legal, '{{ challan.moving_direction|default:"—" }} / {{ challan.legal_direction|default:"—" }}') + '</b></div>' +
        '<div class="cst-kv-r"><span>AI Confidence</span><b>' + v(SAMPLE.conf, '{{ challan.ai_confidence|floatformat:2 }}') + '</b></div>' +
        speed +
        '<div class="cst-kv-r"><span>Fine Amount</span><b class="cst-red">PKR ' + v(SAMPLE.fine, '{{ challan.fine_amount|floatformat:"0" }}') + '/-</b></div>' +
        '</div></div>' + qr + '</div>';
    }
  });

  block('fine_payment', {
    label: 'Fine + Payment Panel', icon: 'bi-cash-coin', desc: 'Amount box + payment channels',
    props: { show_methods: true, due_note: 'Pay within {{ due_days }} days to avoid additional charges and legal action.' },
    schema: [
      { k: 'show_methods', t: 'check', l: 'Show payment methods' },
      { k: 'due_note', t: 'text', l: 'Due note (Django vars allowed)' }
    ],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var methods = p.show_methods ?
        '<div class="cst-pay-grid">' +
        '<div><b>Online</b><span>{{ branding.pay_website }}</span></div>' +
        '<div><b>Mobile Wallets</b><span>JazzCash / EasyPaisa · PSID ' + v(SAMPLE.psid, '{{ challan.psid }}') + '</span></div>' +
        '<div><b>Bank Branches</b><span>Deposit using challan no ' + v(SAMPLE.ticket_no, '{{ challan.ticket_no }}') + '</span></div>' +
        '<div><b>Traffic Office</b><span>Counters at HQ</span></div>' +
        '</div>' : '';
      var note = pv ? p.due_note.replace('{{ due_days }}', SAMPLE.due_days) : p.due_note;
      return '<div class="cst-panel"><div class="cst-panel-h cst-panel-red">Payment Required</div>' +
        '<div class="cst-fine-row"><div class="cst-fine-amt">PKR ' + v(SAMPLE.fine, '{{ challan.fine_amount|floatformat:"0" }}') + '/-</div>' +
        '<div class="cst-fine-words">(' + v(SAMPLE.fine_words, '{{ fine_in_words }}') + ')</div></div>' +
        methods +
        '<div class="cst-due-note">' + esc(note) + '</div></div>';
    }
  });

  block('evidence', {
    label: 'Evidence Frame', icon: 'bi-camera-video', desc: 'Camera frame + plate crop + OSD',
    props: { show_osd: true, show_plate: true, height_mm: 58, title: 'Evidence — 3-Frame Verified' },
    schema: [
      { k: 'title', t: 'text', l: 'Section title' },
      { k: 'show_osd', t: 'check', l: 'Show OSD overlay' },
      { k: 'show_plate', t: 'check', l: 'Show plate crop' },
      { k: 'height_mm', t: 'range', l: 'Height (mm)', min: 35, max: 95, step: 1 }
    ],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var cam = pv ? '<img src="' + SAMPLE.cam_img + '" alt="">' :
        '{% if challan.detection.raw_image %}<img src="file://{{ challan.detection.raw_image.path }}" alt="">{% endif %}';
      var plate = p.show_plate ? (
        pv ? '<img src="' + SAMPLE.plate_img + '" alt="">' :
          '{% if challan.detection.plate_crop_image %}<img src="file://{{ challan.detection.plate_crop_image.path }}" alt="Plate">{% endif %}'
      ) : '';
      var osd = p.show_osd ? '<div class="cst-osd">CAM: ' + v(SAMPLE.camera, '{{ camera_meta.id }}') + '\nTIME: ' + v(SAMPLE.datetime, '{{ camera_meta.timestamp }}') + '\nEVID: 3-frame verified</div>' : '';
      return '<div class="cst-panel cst-evi"><div class="cst-panel-h">' + esc(p.title) + '</div>' +
        '<div class="cst-evi-body" style="min-height:' + p.height_mm + 'mm">' +
        '<div class="cst-cam">' + cam + osd +
        '<div class="cst-bbox" style="left:30%;top:42%;width:16%;height:16%"></div></div>' +
        (p.show_plate ? '<div class="cst-plate">' + plate + '</div>' : '') +
        '</div></div>';
    }
  });

  block('frame_table', {
    label: '3-Frame Evidence Table', icon: 'bi-table', desc: 'Per-frame 1-by-1 verification grid',
    props: { title: 'Frame-by-Frame Evidence Verification (1-by-1)' },
    schema: [{ k: 'title', t: 'text', l: 'Section title' }],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var head = '<tr><th>#</th><th>Plate Read</th><th>Det. Conf</th><th>OCR Conf</th><th>Timestamp</th><th>Full Plate</th></tr>';
      var rows;
      if (pv) {
        rows = SAMPLE.frames.map(function (f) {
          return '<tr><td>' + f.n + '</td><td class="cst-mono">' + f.plate + '</td><td>' + f.conf + '</td><td>' + f.ocr + '</td><td class="cst-mono">' + f.ts + '</td><td class="cst-ok">YES</td></tr>';
        }).join('');
      } else {
        rows = '{% for f in frame_evidence %}<tr><td>{{ f.index }}</td><td class="cst-mono">{{ f.plate }}</td><td>{{ f.confidence|floatformat:2 }}</td><td>{{ f.ocr_confidence|floatformat:2 }}</td><td class="cst-mono">{{ f.timestamp }}</td><td class="{% if f.complete %}cst-ok{% else %}cst-red{% endif %}">{% if f.complete %}YES{% else %}NO{% endif %}</td></tr>{% endfor %}';
      }
      return '<div class="cst-panel"><div class="cst-panel-h">' + esc(p.title) + '</div>' +
        '<table class="cst-table"><thead>' + head + '</thead><tbody>' + rows + '</tbody></table>' +
        '<div class="cst-hash">Track: ' + v(SAMPLE.track, '{{ evidence_summary.track_id }}') +
        ' · Chain hash: ' + v(SAMPLE.hash + '…', '{{ evidence_summary.hash|slice:":16" }}…') +
        ' · Consistency: ' + v('1.00', '{{ evidence_summary.track_consistency|floatformat:2 }}') + '</div></div>';
    }
  });

  block('instructions', {
    label: 'Instructions', icon: 'bi-info-circle', desc: 'Payment & appeal instructions (EN+UR)',
    props: { show_urdu: true },
    schema: [{ k: 'show_urdu', t: 'check', l: 'Show Urdu list' }],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var ur = p.show_urdu ?
        '<ul class="cst-ur">' +
        '<li>چالان جاری ہونے کی تاریخ سے ' + v(SAMPLE.due_days, '{{ due_days }}') + ' دن کے اندر جرمانہ ادا کریں۔</li>' +
        '<li>ادائیگی نہ ہونے کی صورت میں گاڑی ضبط کی جا سکتی ہے۔</li>' +
        '<li>چالان کے خلاف ' + v('15', '{{ appeal_days }}') + ' دن کے اندر اپیل جمع کروائی جا سکتی ہے۔</li></ul>' : '';
      return '<div class="cst-panel cst-ins"><div class="cst-panel-h">Important Instructions</div>' +
        '<ul><li>Pay the fine within ' + v(SAMPLE.due_days, '{{ due_days }}') + ' days from the issue date to avoid additional charges.</li>' +
        '<li>In case of non-payment the vehicle may be impounded as per law.</li>' +
        '<li>Contest this challan within ' + v('15', '{{ appeal_days }}') + ' days at the relevant traffic office.</li>' +
        '<li>Keep this challan for your record. Helpline: ' + v(SAMPLE.helpline, '{{ branding.helpline }}') + '.</li></ul>' + ur + '</div>';
    }
  });

  block('signature', {
    label: 'Officer Signature', icon: 'bi-vector-pen', desc: 'Signature + designation + seal',
    props: { show_seal: true, title: 'Authorized Officer' },
    schema: [
      { k: 'title', t: 'text', l: 'Block title' },
      { k: 'show_seal', t: 'check', l: 'Seal slot' }
    ],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var sig = pv ? '<div class="cst-sigline"></div>' :
        '{% if officer_signature_url %}<img class="cst-sigimg" src="{{ officer_signature_url }}" alt="Signature">{% else %}<div class="cst-sigline"></div>{% endif %}';
      var seal = p.show_seal ? '<div class="cst-seal"><span>SEAL</span></div>' : '';
      return '<div class="cst-sigrow"><div class="cst-sig">' + sig +
        '<div class="cst-sig-name">' + v(SAMPLE.officer, '{{ officer_signature_name|default:"System Generated" }}') + '</div>' +
        '<div class="cst-sig-des">' + v(SAMPLE.designation, '{{ officer_signature_designation|default:"Traffic Officer" }}') + ' · ' + v(SAMPLE.staff_id, '{{ officer_staff_id|default:"—" }}') + '</div>' +
        '</div>' + seal + '</div>';
    }
  });

  block('barcode', {
    label: 'Barcode Strip', icon: 'bi-barcode', desc: 'Code128 ticket barcode',
    props: {},
    schema: [],
    html: function (p, th, pv) {
      if (pv) {
        var bars = '';
        var x = 0;
        for (var i = 0; i < 60; i++) {
          var w = 1 + ((i * 13) % 3);
          bars += '<rect x="' + x + '" y="0" width="' + w + '" height="38" fill="#111"/>';
          x += w + 1 + ((i * 7) % 2);
        }
        return '<div class="cst-bc"><svg viewBox="0 0 ' + x + ' 40" preserveAspectRatio="none">' + bars + '</svg><div>' + SAMPLE.ticket_no + '</div></div>';
      }
      return '<div class="cst-bc">{% if barcode_svg %}{{ barcode_svg|safe }}{% endif %}<div>{{ challan.ticket_no }}</div></div>';
    }
  });

  block('footer', {
    label: 'Footer Bar', icon: 'bi-bottom-half', desc: 'Helpline · website · slogan',
    props: { left: 'Helpline: {{ branding.helpline }}', center: '{{ branding.website }}', right: '{{ branding.footer_slogan_ur }}' },
    schema: [
      { k: 'left', t: 'text', l: 'Left cell' },
      { k: 'center', t: 'text', l: 'Center cell' },
      { k: 'right', t: 'text', l: 'Right cell' }
    ],
    html: function (p, th, pv) {
      function cell(txt) {
        var out = txt
          .replace('{{ branding.helpline }}', SAMPLE.helpline)
          .replace('{{ branding.website }}', SAMPLE.website)
          .replace('{{ branding.footer_slogan_ur }}', 'قانون کی پاسداری');
        return pv ? esc(out) : txt;
      }
      return '<div class="cst-ft" style="background:' + th.primary + '">' +
        '<span>' + cell(p.left) + '</span><span>' + cell(p.center) + '</span><span class="cst-ur-inline">' + cell(p.right) + '</span></div>';
    }
  });

  block('po_copy', {
    label: 'Post Office Copy', icon: 'bi-scissors', desc: 'Cut line + PO counter grid',
    props: {},
    schema: [],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      return '<div class="cst-cut"><span>&#9986;</span><i></i></div>' +
        '<div class="cst-po"><div class="cst-po-title">POST OFFICE COPY</div>' +
        '<div class="cst-po-grid">' +
        '<div><span class="cst-k">TICKET NO.</span><b>' + v(SAMPLE.ticket_no, '{{ challan.ticket_no }}') + '</b></div>' +
        '<div><span class="cst-k">REG. NO.</span><b>' + v(SAMPLE.plate, '{{ challan.plate_number }}') + '</b></div>' +
        '<div><span class="cst-k">NAME</span><b>' + v(SAMPLE.owner, '{{ challan.owner_name|default:"—" }}') + '</b></div>' +
        '<div><span class="cst-k">AMOUNT</span><b>PKR ' + v(SAMPLE.fine, '{{ challan.fine_amount|floatformat:"0" }}') + '/-</b></div>' +
        '<div><span class="cst-k">DUE DATE</span><b>' + v(SAMPLE.due, '{{ challan.due_date|date:"d-M-Y" }}') + '</b></div>' +
        '<div><span class="cst-k">ACCOUNT</span><b>C0263A E-Challans</b></div>' +
        '</div><div class="cst-po-foot"><i>System-generated challan — Safe City enforcement pipeline.</i><span class="cst-po-sig">Cashier: ______________</span></div></div>';
    }
  });

  block('urdu_notice', {
    label: 'Urdu Notice Box', icon: 'bi-card-text', desc: 'Highlighted Urdu legal notice',
    props: {},
    schema: [],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var notice = 'اگر اس ای چالان کے حوالے سے آپ کو کوئی بھی شکایت ہو تو سیف سٹی کی ویب سائٹ پر ٹریفک مجسٹریٹ کی عدالت میں چیلنج کیا جا سکتا ہے۔';
      return '<div class="cst-un"><div class="cst-ur-inline">' + v(notice,
        'اگر اس ای چالان کے حوالے سے آپ کو کوئی بھی شکایت ہو تو سیف سٹی کی ویب سائٹ {{ branding.website }} پر ٹریفک مجسٹریٹ کی عدالت میں چیلنج کیا جا سکتا ہے۔') + '</div></div>';
    }
  });

  block('spacer', {
    label: 'Spacer', icon: 'bi-arrows-expand', desc: 'Vertical gap',
    props: { height_mm: 8 },
    schema: [{ k: 'height_mm', t: 'range', l: 'Height (mm)', min: 2, max: 40, step: 1 }],
    html: function (p) { return '<div style="height:' + p.height_mm + 'mm"></div>'; }
  });

  var AUDIT_SAMPLE = {
    authority_en: 'SAFE CITY — TRAFFIC ENFORCEMENT',
    authority_ur: 'سیف سٹی ٹریفک پولیس',
    office: 'Safe City Authority — Audit & Compliance Wing',
    office_ur: 'آڈٹ و ویژلنس وِنگ',
    doc_no: 'AUD-2026-1011-SUM-005',
    title: 'Periodic Audit Summary Report',
    period: '01 Oct 2026 — 05 Nov 2026',
    officer: 'Ayesha Audit',
    designation: 'Audit Officer',
    staff_id: 'PSC-2026-AUD-005',
    dig: 'Aamir DIG',
    dig_designation: 'Deputy Inspector General (Traffic)',
    issued: '05 Nov 2026',
    prepared: '05 Nov 2026 14:30',
    challans_issued: 128, challans_paid: 96, challans_unpaid: 30, challans_voided: 2,
    detections_total: 420, detections_confirmed: 128, detections_pending: 14,
    detections_rejected: 272, detections_flagged: 6,
    evidence_total: 128, evidence_pass: 126, evidence_rate: '98.4',
    revenue: 192000, revenue_pending: 60000,
    login_success: 214, login_failed: 9, unique_ips: 12, audit_logs: 517,
    top_actions: [
      { a: 'camera.edit', c: 34 }, { a: 'challan.mark_paid', c: 22 },
      { a: 'upload.video', c: 11 }, { a: 'settings.edit', c: 5 }
    ]
  };

  var AUDIT_BLOCKS = {};
  function ablock(type, def) { AUDIT_BLOCKS[type] = def; def.type = type; }

  ablock('a_header', {
    label: 'Authority Header', icon: 'bi-building', desc: 'Logos + authority + office + Urdu',
    props: { office: '', show_urdu: true },
    schema: [{ k: 'office', t: 'text', l: 'Office name (blank = default)' }, { k: 'show_urdu', t: 'check', l: 'Urdu line' }],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var office = p.office || AUDIT_SAMPLE.office;
      return '<div class="cst-hd" style="background:' + th.primary + '">' +
        '<div class="cst-hd-logo"><span>LOGO</span></div>' +
        '<div class="cst-hd-mid"><div class="cst-hd-t">' + v(AUDIT_SAMPLE.authority_en, '{{ branding.authority_name_en }}') + '</div>' +
        '<div class="cst-hd-tag">' + v(esc(office), '{{ branding.office_name }}') + '</div></div>' +
        (p.show_urdu ? '<div class="cst-hd-ur"><div>' + v(AUDIT_SAMPLE.office_ur, 'آڈٹ و ویژلنس وِنگ') + '</div></div>' : '') +
        '<div class="cst-hd-logo"><span>BADGE</span></div></div>';
    }
  });

  ablock('a_refbar', {
    label: 'Reference Bar', icon: 'bi-upc-scan', desc: 'Doc no · classification · date',
    props: {},
    schema: [],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      return '<div class="cst-bar" style="background:' + th.paper + ';color:' + th.ink + ';border:.3mm solid ' + th.line + '">' +
        '<span>Doc No: <b>' + v(AUDIT_SAMPLE.doc_no, '{{ doc_no }}') + '</b></span>' +
        '<span>Classification: <b>Official</b></span>' +
        '<span>Issued: <b>' + v(AUDIT_SAMPLE.issued, '{{ generated_at|date:"d M Y" }}') + '</b></span></div>';
    }
  });

  ablock('a_doctype', {
    label: 'Document Type Banner', icon: 'bi-type-h1', desc: 'Bordered document title',
    props: { title: 'Periodic Audit Summary Report' },
    schema: [{ k: 'title', t: 'text', l: 'Document title' }],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      return '<div class="cst-doctype" style="color:' + th.primary + ';border-color:' + th.primary + '">' +
        v(esc(p.title), esc(p.title)) + '</div>';
    }
  });

  ablock('a_meta', {
    label: 'Period Meta Boxes', icon: 'bi-calendar3', desc: 'Period · officer · prepared',
    props: {},
    schema: [],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      return '<div class="cst-cols cst-cols-3">' +
        '<div class="cst-panel"><div class="cst-kv" style="padding:2mm 2.6mm"><div class="cst-kv-r" style="border:0"><span>Period</span><b>' + v(AUDIT_SAMPLE.period, '{{ period_from|date:"d M Y" }} — {{ period_to|date:"d M Y" }}') + '</b></div></div></div>' +
        '<div class="cst-panel"><div class="cst-kv" style="padding:2mm 2.6mm"><div class="cst-kv-r" style="border:0"><span>Officer</span><b>' + v(AUDIT_SAMPLE.officer, '{{ generated_by_ctx.name }}') + '</b></div></div></div>' +
        '<div class="cst-panel"><div class="cst-kv" style="padding:2mm 2.6mm"><div class="cst-kv-r" style="border:0"><span>Prepared</span><b>' + v(AUDIT_SAMPLE.prepared, '{{ generated_at|date:"d M Y H:i" }}') + '</b></div></div></div>' +
        '</div>';
    }
  });

  ablock('a_stats_table', {
    label: 'Enforcement Summary Table', icon: 'bi-table', desc: 'Challans + detections stats',
    props: { title: '1. Enforcement Summary' },
    schema: [{ k: 'title', t: 'text', l: 'Section title' }],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      function R(k, label, dj) { return '<tr><td>' + label + '</td><td class="n">' + v(AUDIT_SAMPLE[k], dj) + '</td></tr>'; }
      var rows = pv
        ? R('challans_issued', 'E-Challans issued') + R('challans_paid', 'Challans paid') +
          R('detections_total', 'Detections processed') + R('detections_confirmed', 'Detections confirmed')
        : '<tr><td>E-Challans issued</td><td class="n">{{ stats.challans_issued }}</td></tr>' +
          '<tr><td>Challans paid</td><td class="n">{{ stats.challans_paid }}</td></tr>' +
          '<tr><td>Detections processed</td><td class="n">{{ stats.detections_total }}</td></tr>' +
          '<tr><td>Detections confirmed</td><td class="n">{{ stats.detections_confirmed }}</td></tr>';
      return '<div class="cst-panel"><div class="cst-panel-h">' + esc(p.title) + '</div>' +
        '<table class="cst-table"><thead><tr><th>Indicator</th><th>Count</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
    }
  });

  ablock('a_evidence_table', {
    label: 'Evidence Integrity Table', icon: 'bi-shield-check', desc: '5-step verification stats',
    props: { title: 'Evidence Integrity (5-Step Verification)' },
    schema: [{ k: 'title', t: 'text', l: 'Section title' }],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var rows = pv
        ? '<tr><td>Confirmed detections audited</td><td class="n">' + AUDIT_SAMPLE.evidence_total + '</td></tr>' +
          '<tr><td>Full 5/5 pass rate</td><td class="n">' + AUDIT_SAMPLE.evidence_rate + '%</td></tr>' +
          '<tr><td>Flagged for DIG oversight</td><td class="n">' + AUDIT_SAMPLE.detections_flagged + '</td></tr>'
        : '<tr><td>Confirmed detections audited</td><td class="n">{{ stats.evidence_total }}</td></tr>' +
          '<tr><td>Full 5/5 pass rate</td><td class="n">{{ stats.evidence_pass_rate }}%</td></tr>' +
          '<tr><td>Flagged for DIG oversight</td><td class="n">{{ stats.detections_flagged }}</td></tr>';
      return '<div class="cst-panel"><div class="cst-panel-h">' + esc(p.title) + '</div>' +
        '<table class="cst-table"><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
    }
  });

  ablock('a_financial_table', {
    label: 'Financial Position Table', icon: 'bi-cash-stack', desc: 'Revenue collected / pending',
    props: { title: 'Financial Position' },
    schema: [{ k: 'title', t: 'text', l: 'Section title' }],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var rows = pv
        ? '<tr><td>Revenue collected</td><td class="n">PKR ' + AUDIT_SAMPLE.revenue.toLocaleString() + '</td></tr>' +
          '<tr><td>Revenue pending</td><td class="n">PKR ' + AUDIT_SAMPLE.revenue_pending.toLocaleString() + '</td></tr>'
        : '<tr><td>Revenue collected</td><td class="n">PKR {{ stats.revenue_collected|floatformat:"0" }}</td></tr>' +
          '<tr><td>Revenue pending</td><td class="n">PKR {{ stats.revenue_pending|floatformat:"0" }}</td></tr>';
      return '<div class="cst-panel"><div class="cst-panel-h">' + esc(p.title) + '</div>' +
        '<table class="cst-table"><thead><tr><th>Head</th><th>Amount (PKR)</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
    }
  });

  ablock('a_login_table', {
    label: 'Auth Activity Table', icon: 'bi-shield-lock', desc: 'Logins, failures, IPs, actions',
    props: { title: 'Authentication Activity' },
    schema: [{ k: 'title', t: 'text', l: 'Section title' }],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var rows = pv
        ? '<tr><td>Successful logins</td><td class="n">' + AUDIT_SAMPLE.login_success + '</td></tr>' +
          '<tr><td>Failed attempts</td><td class="n">' + AUDIT_SAMPLE.login_failed + '</td></tr>' +
          '<tr><td>Unique source IPs</td><td class="n">' + AUDIT_SAMPLE.unique_ips + '</td></tr>' +
          '<tr><td>Audited actions</td><td class="n">' + AUDIT_SAMPLE.audit_logs + '</td></tr>'
        : '<tr><td>Successful logins</td><td class="n">{{ stats.login_success }}</td></tr>' +
          '<tr><td>Failed attempts</td><td class="n">{{ stats.login_failed }}</td></tr>' +
          '<tr><td>Unique source IPs</td><td class="n">{{ stats.unique_ip_count }}</td></tr>' +
          '<tr><td>Audited actions</td><td class="n">{{ stats.audit_log_count }}</td></tr>';
      var actions = pv
        ? AUDIT_SAMPLE.top_actions.map(function (t) { return '<tr><td>' + t.a + '</td><td class="n">' + t.c + '</td></tr>'; }).join('')
        : '{% for a in stats.top_actions %}<tr><td>{{ a.action }}</td><td class="n">{{ a.c }}</td></tr>{% endfor %}';
      return '<div class="cst-panel"><div class="cst-panel-h">' + esc(p.title) + '</div>' +
        '<table class="cst-table"><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>' + rows + '</tbody></table>' +
        '<table class="cst-table" style="margin-top:2mm"><thead><tr><th>Most Frequent Action</th><th>Count</th></tr></thead><tbody>' + actions + '</tbody></table></div>';
    }
  });

  ablock('a_finding', {
    label: 'Observation / Finding', icon: 'bi-card-checklist', desc: 'Bordered finding box',
    props: { label: 'F1 — Chain integrity.', text: 'Every confirmed detection carries a SHA-256 evidence-chain digest; no tampering signals detected.' },
    schema: [
      { k: 'label', t: 'text', l: 'Finding label' },
      { k: 'text', t: 'text', l: 'Finding text' }
    ],
    html: function (p, th, pv) {
      return '<div class="cst-finding" style="border-left-color:' + th.primary + '"><b>' + esc(p.label) + '</b> ' + esc(p.text) + '</div>';
    }
  });

  ablock('a_body_text', {
    label: 'Letter Body Text', icon: 'bi-text-paragraph', desc: 'Paragraph block (letter style)',
    props: { text: 'The enforcement pipeline operated in compliance with the prescribed five-step evidence verification standard during the period under review.' },
    schema: [{ k: 'text', t: 'text', l: 'Paragraph' }],
    html: function (p) {
      return '<div class="cst-letter">' + esc(p.text) + '</div>';
    }
  });

  ablock('a_signature', {
    label: 'Dual Signature Block', icon: 'bi-vector-pen', desc: 'Audit officer + DIG countersign',
    props: {},
    schema: [],
    html: function (p, th, pv) {
      var v = function (s, d) { return pv ? s : d; };
      var sig = pv ? '<div class="cst-sigline"></div>' :
        '{% if generated_by_ctx.signature_url %}<img class="cst-sigimg" src="{{ generated_by_ctx.signature_url }}" alt="Signature">{% else %}<div class="cst-sigline"></div>{% endif %}';
      var csig = pv ? '<div class="cst-sigline"></div>' :
        '{% if countersigned_by_ctx.signature_url %}<img class="cst-sigimg" src="{{ countersigned_by_ctx.signature_url }}" alt="Signature">{% else %}<div class="cst-sigline"></div>{% endif %}';
      return '<div class="cst-cols cst-cols-2">' +
        '<div class="cst-sigbox"><div class="cst-sigwrap">' + sig + '</div>' +
        '<div class="cst-sig-name">' + v(AUDIT_SAMPLE.officer, '{{ generated_by_ctx.name }}') + '</div>' +
        '<div class="cst-sig-des">' + v(AUDIT_SAMPLE.designation, '{{ generated_by_ctx.designation }} · {{ generated_by_ctx.staff_id }}') + '</div>' +
        '<div class="cst-sig-des">Audit Officer</div></div>' +
        '<div class="cst-sigbox"><div class="cst-sigwrap">' + csig + '</div>' +
        '<div class="cst-sig-name">' + v(AUDIT_SAMPLE.dig, '{{ countersigned_by_ctx.name }}') + '</div>' +
        '<div class="cst-sig-des">' + v(AUDIT_SAMPLE.dig_designation, '{{ countersigned_by_ctx.designation }} · {{ countersigned_by_ctx.staff_id }}') + '</div>' +
        '<div class="cst-sig-des">Countersigned — DIG</div></div></div>';
    }
  });

  ablock('a_seal', {
    label: 'Audit Verified Seal', icon: 'bi-patch-check', desc: 'Rotated stamp badge',
    props: { top: 'AUDIT VERIFIED', sub: 'AUDIT & VIGILANCE WING' },
    schema: [
      { k: 'top', t: 'text', l: 'Seal main text' },
      { k: 'sub', t: 'text', l: 'Seal sub text' }
    ],
    html: function (p, th) {
      return '<div class="cst-seal-badge" style="border-color:' + th.red + ';color:' + th.red + '">' +
        '<div class="cst-seal-t">' + esc(p.top) + '</div><div class="cst-seal-s">' + esc(p.sub) + '</div></div>';
    }
  });

  ablock('a_footer', {
    label: 'Footer Bar', icon: 'bi-bottom-half', desc: 'Authority · web · hash note',
    props: {},
    schema: [],
    html: function (p, th, pv) {
      return '<div class="cst-ft" style="background:' + th.paper + ';color:' + th.muted + ';border-top:.3mm solid ' + th.line + '">' +
        '<span>{{ branding.authority_name_en }}</span><span>{{ branding.website }}</span>' +
        '<span>System generated · verifiable via document hash</span></div>';
    }
  });

  var AUDIT_STARTERS = {
    audit_summary_report: ['a_header', 'a_refbar', 'a_doctype', 'a_meta', 'a_stats_table', 'a_evidence_table', 'a_financial_table', 'a_finding', 'a_signature', 'a_footer'],
    compliance_certificate: ['a_header', 'a_refbar', 'a_doctype', 'a_meta', 'a_body_text', 'a_evidence_table', 'a_stats_table', 'a_seal', 'a_signature', 'a_footer'],
    financial_audit_statement: ['a_header', 'a_refbar', 'a_doctype', 'a_meta', 'a_financial_table', 'a_finding', 'a_signature', 'a_footer'],
    security_incident_report: ['a_header', 'a_refbar', 'a_doctype', 'a_meta', 'a_login_table', 'a_evidence_table', 'a_finding', 'a_signature', 'a_footer'],
    operational_review_letter: ['a_header', 'a_refbar', 'a_body_text', 'a_stats_table', 'a_finding', 'a_body_text', 'a_signature', 'a_footer'],
  };

  var ACTIVE_BLOCKS = IS_CHALLAN ? BLOCKS : AUDIT_BLOCKS;
  var ACTIVE_STARTERS = IS_CHALLAN ? STARTER_COMPOSITIONS : AUDIT_STARTERS;

  var DEFAULT_THEME = {
    primary: '#0b3a78', red: '#d3202a', ink: '#14233a', line: '#cfdbea',
    paper: '#fdfdfd', font_scale: 1, padding_mm: 6, radius_mm: 2, framed: true
  };

  var THEME_SCHEMA = [
    { k: 'primary', t: 'color', l: 'Primary (navy)' },
    { k: 'red', t: 'color', l: 'Accent (red)' },
    { k: 'ink', t: 'color', l: 'Ink text' },
    { k: 'line', t: 'color', l: 'Border lines' },
    { k: 'paper', t: 'color', l: 'Paper' },
    { k: 'font_scale', t: 'range', l: 'Font scale', min: 0.8, max: 1.3, step: 0.05 },
    { k: 'padding_mm', t: 'range', l: 'Sheet padding (mm)', min: 3, max: 12, step: 1 },
    { k: 'radius_mm', t: 'range', l: 'Corner radius (mm)', min: 0, max: 5, step: 0.5 },
    { k: 'framed', t: 'check', l: 'Outer border frame' }
  ];

  function shellCss(th, forPdf) {
    var fonts = forPdf ?
      "@font-face{font-family:'Noto Nastaliq Urdu';src:url('static/fonts/NotoNastaliqUrdu-Regular.ttf');font-weight:400}" +
      "@font-face{font-family:'Noto Nastaliq Urdu';src:url('static/fonts/NotoNastaliqUrdu-Bold.ttf');font-weight:700}" +
      "@font-face{font-family:'Noto Naskh Arabic';src:url('static/fonts/NotoNaskhArabic-Regular.ttf');font-weight:400}" : '';
    var page = forPdf ? '@page{size:A4 portrait;margin:0}' : '';
    return fonts + page +
      '.cst-sheet{width:210mm;min-height:297mm;background:' + th.paper + ';padding:' + th.padding_mm + 'mm;' +
      'display:flex;flex-direction:column;gap:2.2mm;box-sizing:border-box;' +
      'font-family:Arial,Helvetica,sans-serif;color:' + th.ink + ';font-size:' + (th.font_scale * 8.2) + 'pt;' +
      (th.framed ? 'border:1px solid ' + th.line + ';' : '') + '}' +
      '.cst-hd{display:flex;align-items:center;gap:3mm;padding:3mm 5mm;border-radius:' + th.radius_mm + 'mm;color:#fff}' +
      '.cst-hd-logo{width:20mm;height:20mm;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;font-size:5pt;color:#94a3b8;font-weight:700}' +
      '.cst-hd-mid{flex:1;text-align:center}' +
      '.cst-hd-t{font-size:13.5pt;font-weight:800;letter-spacing:.02em;text-transform:uppercase;line-height:1.15}' +
      '.cst-hd-tag{font-size:6pt;letter-spacing:.1em;text-transform:uppercase;opacity:.85;margin-top:1mm}' +
      '.cst-hd-ur{text-align:center;font-family:"Noto Nastaliq Urdu",serif;direction:rtl;font-size:10.5pt;line-height:1.7}' +
      '.cst-hd-tag-ur{font-size:7pt;opacity:.85;border-top:.25mm solid rgba(255,255,255,.5);margin-top:.8mm;padding-top:.8mm}' +
      '.cst-bar{display:grid;grid-template-columns:1fr 1fr 1fr;padding:2mm 4mm;border-radius:' + th.radius_mm + 'mm;color:#fff;font-size:8pt}' +
      '.cst-bar span:nth-child(2){text-align:center}.cst-bar span:nth-child(3){text-align:right}' +
      '.cst-cols{display:grid;gap:2.4mm}.cst-cols-1{grid-template-columns:1fr}.cst-cols-2{grid-template-columns:1fr 1fr}' +
      '.cst-panel{border:.3mm solid ' + th.line + ';border-radius:' + th.radius_mm + 'mm;background:#fff;overflow:hidden;display:flex;flex-direction:column}' +
      '.cst-panel-h{background:' + th.primary + ';color:#fff;padding:1.6mm 2.6mm;font-size:7pt;font-weight:800;text-transform:uppercase;letter-spacing:.04em}' +
      '.cst-panel-red{background:' + th.red + '}' +
      '.cst-kv{display:flex;flex-direction:column}' +
      '.cst-kv-r{display:flex;justify-content:space-between;gap:2mm;padding:1.3mm 2.6mm;border-bottom:.22mm solid #eef2f7;font-size:7.4pt}' +
      '.cst-kv-r:last-child{border-bottom:0}' +
      '.cst-kv-r span{color:#64748b;font-weight:600}.cst-kv-r b{font-weight:700;text-align:right}' +
      '.cst-red{color:' + th.red + '}' +
      '.cst-qrbox{border:.3mm solid ' + th.line + ';border-radius:' + th.radius_mm + 'mm;padding:2.4mm;text-align:center;background:#fff}' +
      '.cst-qr{width:24mm;height:24mm;margin:0 auto;border:1px solid ' + th.line + ';border-radius:1mm;overflow:hidden}' +
      '.cst-qr img{width:100%;height:100%;object-fit:contain}' +
      '.cst-qr-cap{font-size:7pt;font-weight:700;color:' + th.primary + ';margin-top:1.2mm}' +
      '.cst-qr-psid{font-size:6.6pt;color:#64748b;margin-top:.6mm}' +
      '.cst-fine-row{padding:2.4mm;text-align:center;border-bottom:.3mm solid ' + th.red + '}' +
      '.cst-fine-amt{font-size:16pt;font-weight:900;color:' + th.red + '}' +
      '.cst-fine-words{font-size:6.8pt;color:#64748b;margin-top:.8mm}' +
      '.cst-pay-grid{display:grid;grid-template-columns:repeat(4,1fr);padding:1.8mm}' +
      '.cst-pay-grid div{display:flex;flex-direction:column;gap:.6mm;padding:1.4mm;border-left:.22mm solid ' + th.line + ';font-size:6.6pt}' +
      '.cst-pay-grid div:first-child{border-left:0}' +
      '.cst-pay-grid b{color:' + th.primary + ';font-size:7pt}' +
      '.cst-due-note{margin:1.6mm;padding-top:1.4mm;border-top:.22mm solid ' + th.line + ';font-size:6.2pt;color:#64748b;text-align:center}' +
      '.cst-evi-body{display:grid;grid-template-columns:1fr 34mm;gap:2mm;padding:2mm;flex:1}' +
      '.cst-cam{position:relative;background:#3a3d42;border-radius:1mm;overflow:hidden;min-height:30mm}' +
      '.cst-cam img{width:100%;height:100%;object-fit:cover;display:block}' +
      '.cst-osd{position:absolute;top:0;left:0;background:rgba(0,0,0,.82);color:#fff;font-family:monospace;font-size:6.6pt;line-height:1.3;padding:1mm 1.6mm;white-space:pre}' +
      '.cst-bbox{position:absolute;border:.35mm solid #e22;left:30%;top:42%;width:16%;height:16%}' +
      '.cst-plate{background:#222;border-radius:1mm;overflow:hidden;display:flex;align-items:center;justify-content:center}' +
      '.cst-plate img{width:100%;object-fit:contain}' +
      '.cst-table{width:100%;border-collapse:collapse;font-size:6.8pt}' +
      '.cst-table th{background:' + th.primary + ';color:#fff;padding:1.2mm;text-align:left;font-size:6.4pt;text-transform:uppercase}' +
      '.cst-table td{padding:1.2mm;border-bottom:.22mm solid #eef2f7}' +
      '.cst-table td.cst-mono{font-family:monospace;font-weight:700}' +
      '.cst-ok{color:#15803d;font-weight:800}' +
      '.cst-hash{padding:1.4mm 2.4mm;font-size:6pt;color:#64748b;font-family:monospace;border-top:.22mm solid ' + th.line + '}' +
      '.cst-ins ul{padding:1.6mm 3mm 1.6mm 7mm;font-size:6.6pt;line-height:1.5}' +
      '.cst-ins ul.cst-ur{direction:rtl;padding:0 7mm 1.6mm 3mm;font-family:"Noto Nastaliq Urdu",serif;font-size:6.8pt;line-height:1.9}' +
      '.cst-sigrow{display:flex;align-items:center;justify-content:space-between;gap:3mm;padding:3mm}' +
      '.cst-sig{text-align:center;flex:1}' +
      '.cst-sigline{height:11mm;border-bottom:.3mm dotted #64748b;width:44mm;margin:0 auto}' +
      '.cst-sigimg{max-height:11mm;max-width:44mm;margin:0 auto;display:block}' +
      '.cst-sig-name{font-weight:800;font-size:7.6pt;margin-top:1.2mm}' +
      '.cst-sig-des{font-size:6.6pt;color:#64748b}' +
      '.cst-seal{width:22mm;height:22mm;border:2px dashed #94a3b8;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:5.4pt;color:#94a3b8;font-weight:800}' +
      '.cst-bc{text-align:center;padding:2mm}' +
      '.cst-bc svg{height:9mm;max-width:60mm}' +
      '.cst-bc div{font-size:7pt;letter-spacing:.14em;margin-top:1mm;font-family:monospace}' +
      '.cst-ft{display:grid;grid-template-columns:1fr 1fr 1fr;color:#fff;padding:2.2mm 4mm;border-radius:' + th.radius_mm + 'mm;font-size:7.4pt;text-align:center}' +
      '.cst-ur-inline{font-family:"Noto Nastaliq Urdu",serif;direction:rtl}' +
      '.cst-cut{display:flex;align-items:center;gap:1.5mm;margin:2.4mm 0 .6mm;color:#475569;font-size:10pt}' +
      '.cst-cut i{flex:1;border-top:.35mm dashed #7a8088}' +
      '.cst-po{border:.35mm solid #94a3b8;border-radius:' + th.radius_mm + 'mm;padding:2.6mm 4mm;background:#fff}' +
      '.cst-po-title{text-align:center;font-weight:900;font-size:9pt;letter-spacing:.05em;margin-bottom:2mm}' +
      '.cst-po-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1.6mm 5mm;font-size:7pt}' +
      '.cst-po-grid .cst-k{display:block;font-size:5.8pt;font-weight:800;color:#64748b;letter-spacing:.06em}' +
      '.cst-po-foot{display:flex;justify-content:space-between;align-items:flex-end;border-top:.4mm solid ' + th.ink + ';margin-top:2.4mm;padding-top:1.4mm;font-size:5.8px}' +
      '.cst-po-sig{font-weight:700}' +
      '.cst-un{background:#fdeaea;border:.3mm solid #d9534f;border-radius:' + th.radius_mm + 'mm;padding:2.4mm 5mm;font-size:7.6pt;line-height:2;text-align:center}' +
      '.cst-cols-3{grid-template-columns:1fr 1fr 1fr}' +
      '.cst-doctype{text-align:center;margin:6mm 0 2mm}' +
      '.cst-doctype>*{display:inline-block;font-size:12.5pt;font-weight:800;letter-spacing:.12em;text-transform:uppercase;border:1.6px solid currentColor;padding:2mm 8mm;border-radius:1mm}' +
      '.cst-finding{border-left:3px solid ' + th.primary + ';background:#f6f9fd;padding:2.6mm 3.4mm;margin:2.4mm 0;font-size:8.2pt;line-height:1.5}' +
      '.cst-finding b{color:' + th.primary + '}' +
      '.cst-letter{font-size:9pt;line-height:1.85;text-align:justify;text-indent:8mm;padding:1mm 0}' +
      '.cst-sigbox{border:.3mm solid ' + th.line + ';border-radius:' + th.radius_mm + 'mm;padding:3mm;text-align:center;background:#fff}' +
      '.cst-sigwrap{height:14mm;display:flex;align-items:flex-end;justify-content:center}' +
      '.cst-seal-badge{margin:5mm auto 0;width:44mm;border:2.2px solid ' + th.red + ';color:' + th.red + ';border-radius:2mm;text-align:center;padding:2.4mm 2mm;transform:rotate(-4deg)}' +
      '.cst-seal-t{font-size:10.5pt;font-weight:900;letter-spacing:.14em}' +
      '.cst-seal-s{font-size:6.6pt;letter-spacing:.1em;margin-top:1mm}' +
      '.cst-mono{font-family:monospace}';
  }

  function blockHtml(b, th, preview) {
    var def = ACTIVE_BLOCKS[b.type];
    if (!def) return '';
    return def.html(b.props || {}, th, preview);
  }

  function buildSheetHtml(doc, preview, forPdf) {
    var inner = doc.blocks.map(function (b) { return blockHtml(b, doc.theme, preview); }).join('\n');
    if (preview) {
      return '<style>' + shellCss(doc.theme, false) + '</style>' +
        '<div class="cst-sheet">' + (inner || '<div style="text-align:center;color:#94a3b8;padding-top:120mm">Empty canvas — add blocks from the left palette</div>') + '</div>';
    }
    return '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<title>E-Challan {{ challan.ticket_no }}</title>\n' +
      '<style>\n' + shellCss(doc.theme, true) + '\n</style>\n</head>\n<body>\n<div class="cst-sheet">\n' + inner + '\n</div>\n</body>\n</html>\n';
  }

  var doc = null;
  var selectedIdx = -1;
  var zoom = 0.62;
  var dirty = false;
  var templatesData = [];

  var els = {};
  function $(id) { return document.getElementById(id); }

  function setDirty(v) {
    dirty = v;
    if (els.dirtyBadge) els.dirtyBadge.hidden = !v;
  }

  function newDoc(name, blockTypes) {
    var defaults = IS_CHALLAN
      ? ['header', 'meta_bar', 'vehicle_owner', 'violation', 'evidence', 'frame_table', 'fine_payment', 'instructions', 'signature', 'footer']
      : ['a_header', 'a_refbar', 'a_doctype', 'a_meta', 'a_stats_table', 'a_evidence_table', 'a_financial_table', 'a_finding', 'a_signature', 'a_footer'];
    var blocks = (blockTypes || defaults).map(function (t) {
      var d = ACTIVE_BLOCKS[t];
      var props = {};
      Object.keys(d.props || {}).forEach(function (k) { props[k] = d.props[k]; });
      return { type: t, props: props };
    });
    return { id: null, name: name || 'Untitled Design', theme: JSON.parse(JSON.stringify(DEFAULT_THEME)), blocks: blocks };
  }

  function renderPalette() {
    var host = els.paletteList;
    host.innerHTML = '';
    Object.keys(ACTIVE_BLOCKS).forEach(function (type) {
      var d = ACTIVE_BLOCKS[type];
      var item = document.createElement('div');
      item.className = 'cs-pal-item';
      item.draggable = true;
      item.innerHTML = '<i class="bi ' + d.icon + '"></i><span>' + d.label + '<small>' + d.desc + '</small></span>';
      item.addEventListener('click', function () { addBlock(type); });
      item.addEventListener('dragstart', function (ev) { ev.dataTransfer.setData('text/cst-block', type); });
      host.appendChild(item);
    });
  }

  function renderThemeProps() {
    var host = els.themeProps;
    host.innerHTML = '';
    THEME_SCHEMA.forEach(function (f) {
      host.appendChild(propControl(f, doc.theme, function () { setDirty(true); renderCanvas(); }));
    });
  }

  function propControl(f, target, onChange) {
    var wrap = document.createElement('div');
    wrap.className = 'cs-prop-row';
    if (f.t === 'check') {
      wrap.className = 'cs-prop-check';
      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = !!target[f.k];
      cb.id = 'pc_' + f.k;
      cb.addEventListener('change', function () { target[f.k] = cb.checked; onChange(); });
      var lab = document.createElement('label');
      lab.htmlFor = cb.id;
      lab.textContent = f.l;
      wrap.appendChild(cb);
      wrap.appendChild(lab);
      return wrap;
    }
    var lab = document.createElement('label');
    lab.textContent = f.l;
    wrap.appendChild(lab);
    var input;
    if (f.t === 'select') {
      input = document.createElement('select');
      (f.opts || []).forEach(function (o) {
        var opt = document.createElement('option');
        opt.value = o[0];
        opt.textContent = o[1];
        input.appendChild(opt);
      });
      input.value = String(target[f.k]);
      input.addEventListener('change', function () { target[f.k] = input.value; onChange(); });
    } else {
      input = document.createElement('input');
      input.type = f.t === 'color' ? 'color' : (f.t === 'range' ? 'range' : 'text');
      input.value = target[f.k];
      if (f.t === 'range') { input.min = f.min; input.max = f.max; input.step = f.step; }
      input.addEventListener('input', function () {
        target[f.k] = f.t === 'range' ? parseFloat(input.value) : input.value;
        onChange();
      });
    }
    wrap.appendChild(input);
    return wrap;
  }

  function renderProps() {
    var host = els.propsBody;
    host.innerHTML = '';
    if (selectedIdx < 0 || !doc.blocks[selectedIdx]) {
      host.innerHTML = '<div class="cs-props-empty">Select a block on the canvas to edit its properties.</div>';
      return;
    }
    var b = doc.blocks[selectedIdx];
    var d = ACTIVE_BLOCKS[b.type];
    var head = document.createElement('div');
    head.className = 'cs-props-head';
    head.innerHTML = '<i class="bi ' + d.icon + '"></i>' + d.label;
    host.appendChild(head);
    var sub = document.createElement('div');
    sub.className = 'cs-props-sub';
    sub.textContent = d.desc;
    host.appendChild(sub);
    (d.schema || []).forEach(function (f) {
      host.appendChild(propControl(f, b.props, function () { setDirty(true); renderCanvas(); }));
    });
  }

  function renderCanvas() {
    var canvas = els.canvas;
    if (!doc.blocks.length) {
      canvas.classList.add('cs-empty-canvas');
      canvas.innerHTML = '<i class="bi bi-plus-square-dotted"></i><div>Canvas is empty</div><div style="font-size:.8rem;font-weight:500">Click blocks in the left palette to compose your challan</div>';
      return;
    }
    canvas.classList.remove('cs-empty-canvas');
    canvas.innerHTML = '';
    var styleTag = document.createElement('style');
    styleTag.textContent = shellCss(doc.theme, false) +
      '#csCanvas.cst-sheet{width:100%;min-height:auto;height:auto;box-shadow:none;border-radius:2mm;' +
      'padding:' + doc.theme.padding_mm + 'mm;transform:scale(1)}';
    canvas.appendChild(styleTag);
    var blocksHost = canvas;

    doc.blocks.forEach(function (b, i) {
      var def = ACTIVE_BLOCKS[b.type] || BLOCKS[b.type];
      var wrap = document.createElement('div');
      wrap.className = 'cs-block' + (i === selectedIdx ? ' is-selected' : '');
      wrap.dataset.idx = i;
      wrap.innerHTML =
        '<div class="cs-block-label">' + def.label + '</div>' +
        '<div class="cs-block-tools">' +
        '<button type="button" data-act="up" title="Move up"><i class="bi bi-arrow-up"></i></button>' +
        '<button type="button" data-act="down" title="Move down"><i class="bi bi-arrow-down"></i></button>' +
        '<button type="button" data-act="del" title="Remove block"><i class="bi bi-x-lg"></i></button>' +
        '</div>' +
        '<div class="cs-block-body">' + blockHtml(b, doc.theme, true) + '</div>';
      wrap.addEventListener('click', function (ev) {
        var act = ev.target.closest('[data-act]');
        if (act) {
          ev.stopPropagation();
          var a = act.dataset.act;
          if (a === 'up' && i > 0) {
            doc.blocks.splice(i - 1, 0, doc.blocks.splice(i, 1)[0]);
            selectedIdx = i - 1;
          } else if (a === 'down' && i < doc.blocks.length - 1) {
            doc.blocks.splice(i + 1, 0, doc.blocks.splice(i, 1)[0]);
            selectedIdx = i + 1;
          } else if (a === 'del') {
            doc.blocks.splice(i, 1);
            selectedIdx = -1;
          }
          setDirty(true);
          renderCanvas();
          renderProps();
          return;
        }
        selectedIdx = i;
        renderCanvas();
        renderProps();
      });
      blocksHost.appendChild(wrap);
    });
    applyZoom();
  }

  function applyZoom() {
    els.canvas.style.transform = 'scale(' + zoom + ')';
    els.zoomVal.textContent = Math.round(zoom * 100) + '%';
  }

  function addBlock(type) {
    var d = ACTIVE_BLOCKS[type];
    var props = {};
    Object.keys(d.props || {}).forEach(function (k) { props[k] = d.props[k]; });
    doc.blocks.push({ type: type, props: props });
    selectedIdx = doc.blocks.length - 1;
    setDirty(true);
    renderCanvas();
    renderProps();
  }

  function showPanel(which) {
    document.querySelectorAll('[data-cs-panel]').forEach(function (p) {
      p.classList.toggle('is-hidden', p.dataset.csPanel !== which);
    });
    document.querySelectorAll('.cs-tab').forEach(function (t) {
      t.classList.toggle('is-active', t.dataset.csTab === which);
    });
  }

  function openEditor(d) {
    doc = d;
    selectedIdx = -1;
    els.name.value = doc.name || '';
    setDirty(false);
    renderThemeProps();
    renderCanvas();
    renderProps();
    showPanel('editor');
    els.canvasScroll.scrollTop = 0;
  }

  function collectAndSubmit(activate) {
    doc.name = els.name.value.trim() || 'Untitled Design';
    var html = buildSheetHtml(doc, false, true);
    $('csFormId').value = doc.id || '';
    $('csFormName').value = doc.name;
    $('csFormHtml').value = html;
    $('csFormDesign').value = JSON.stringify(doc);
    $('csFormActivate').value = activate ? '1' : '0';
    els.saveForm.submit();
  }

  function submitPreview() {
    doc.name = els.name.value.trim();
    var html = buildSheetHtml(doc, false, true);
    $('csPreviewHtml').value = html;
    els.previewForm.submit();
  }

  function loadTemplatesData(cb) {
    fetch(els.studioDataUrl, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) { templatesData = d.items || []; if (cb) cb(); })
      .catch(function () { templatesData = []; if (cb) cb(); });
  }

  function editTemplate(id) {
    var t = templatesData.filter(function (x) { return x.kind === 'db' && String(x.id) === String(id); })[0];
    if (!t) return;
    if (t.has_design && t.design) {
      try {
        var d = JSON.parse(t.design);
        d.id = t.id;
        openEditor(d);
        return;
      } catch (e) { /* fall through to blank */ }
    }
    openEditor(newDoc(t.name + ' (redesign)'));
  }

  function branchBuiltin(key) {
    var comp = ACTIVE_STARTERS[key] || null;
    openEditor(newDoc(key.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); }) + ' — Redesign', comp));
  }

  function thumbs() {
    document.querySelectorAll('[data-cs-thumb]').forEach(function (el) {
      var raw = el.dataset.csThumb || '';
      if (!raw) {
        el.innerHTML = '<div style="display:flex;height:100%;align-items:center;justify-content:center;color:#94a3b8;font-size:.75rem">No preview (structured design — open editor)</div>';
        return;
      }
      var f = document.createElement('iframe');
      f.setAttribute('sandbox', '');
      f.srcdoc = raw;
      el.appendChild(f);
      var scale = Math.min(el.clientWidth / 794, el.clientHeight / 1123);
      f.style.transform = 'scale(' + scale + ')';
    });
  }

  function bindGalleryThumbs() {
    document.querySelectorAll('[data-cs-thumb]').forEach(function (el) {
      var ro = new ResizeObserver(function () {
        var f = el.querySelector('iframe');
        if (f) {
          var scale = Math.min(el.clientWidth / 794, el.clientHeight / 1123);
          f.style.transform = 'scale(' + scale + ')';
        }
      });
      ro.observe(el);
    });
  }

  function init() {
    els = {
      paletteList: $('csPaletteList'),
      themeProps: $('csThemeProps'),
      propsBody: $('csPropsBody'),
      canvas: $('csCanvas'),
      canvasScroll: $('csCanvasScroll'),
      name: $('csName'),
      dirtyBadge: $('csDirtyBadge'),
      zoomVal: $('csZoomVal'),
      saveForm: $('csSaveForm'),
      previewForm: $('csPreviewForm'),
      studioDataUrl: document.querySelector('link[data-cs-data-url]') ? document.querySelector('link[data-cs-data-url]').href : window.location.href
    };
    els.studioDataUrl = document.body.dataset.csDataUrl || (window.location.pathname.replace(/\/$/, '') + '/data/');

    doc = newDoc(null);

    document.querySelectorAll('[data-cs-tab]').forEach(function (t) {
      t.addEventListener('click', function () { showPanel(t.dataset.csTab); });
    });
    document.querySelectorAll('[data-cs-new]').forEach(function (b) {
      b.addEventListener('click', function () { openEditor(newDoc(null)); });
    });
    document.querySelectorAll('[data-cs-edit]').forEach(function (b) {
      b.addEventListener('click', function () {
        loadTemplatesData(function () { editTemplate(b.dataset.csEdit); });
      });
    });
    document.querySelectorAll('[data-cs-branch]').forEach(function (b) {
      b.addEventListener('click', function () { branchBuiltin(b.dataset.csBranch); });
    });
    document.querySelectorAll('[data-cs-back]').forEach(function (b) {
      b.addEventListener('click', function () {
        if (!dirty || window.confirm('You have unsaved changes. Leave the editor anyway?')) {
          window.location.reload();
        }
      });
    });

    $('csSaveBtn').addEventListener('click', function () { collectAndSubmit(false); });
    $('csSaveActiveBtn').addEventListener('click', function () {
      if (window.confirm('Save this design and make it the ACTIVE challan template for all newly generated challans?')) {
        collectAndSubmit(true);
      }
    });
    $('csPreviewBtn').addEventListener('click', submitPreview);
    $('csZoomIn').addEventListener('click', function () { zoom = Math.min(1.4, zoom + 0.08); applyZoom(); });
    $('csZoomOut').addEventListener('click', function () { zoom = Math.max(0.3, zoom - 0.08); applyZoom(); });
    els.name.addEventListener('input', function () { setDirty(true); });

    els.canvas.addEventListener('dragover', function (ev) { ev.preventDefault(); });
    els.canvas.addEventListener('drop', function (ev) {
      ev.preventDefault();
      var type = ev.dataTransfer.getData('text/cst-block');
      if (type && ACTIVE_BLOCKS[type]) addBlock(type);
    });

    renderPalette();
    thumbs();
    bindGalleryThumbs();
    window.addEventListener('beforeunload', function (ev) {
      if (dirty) { ev.preventDefault(); ev.returnValue = ''; }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
