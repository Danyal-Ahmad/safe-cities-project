(function () {
  'use strict';

  var DS_STYLES = [
    "    body { font-family: 'Inter', Arial, sans-serif; font-size: 11px; color: #1F2937; background: #F1F3F5; padding: 16px; }",
    "    .sheet { width: 210mm; min-height: 297mm; margin: 0 auto; padding: 12mm; background: #FFFFFF; box-shadow: 0 4px 18px rgba(0,0,0,.15); }",
    "    .ds-block { margin-bottom: 14px; }",
    "    .ds-header { display: flex; align-items: center; gap: 14px; border-bottom: 3px double #1d4f7c; padding-bottom: 10px; margin-bottom: 14px; }",
    "    .ds-header img { width: 58px; height: 58px; }",
    "    .ds-header h1 { font-size: 17px; color: #1d4f7c; margin: 0; font-weight: 800; }",
    "    .ds-header .ds-sub { font-size: 10px; color: #6b7280; margin-top: 2px; }",
    "    .ds-stamp { display: inline-block; padding: 4px 10px; border: 2px solid #15803d; color: #15803d; font-weight: 800; transform: rotate(-6deg); border-radius: 4px; font-size: 12px; letter-spacing: .1em; margin-left: auto; }",
    "    .ds-grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }",
    "    .ds-box { border: 1px solid #e5e7eb; border-radius: 6px; padding: 10px; background: #f8fafc; text-align: center; }",
    "    .ds-box .ds-k { font-size: 9px; color: #6b7280; text-transform: uppercase; letter-spacing: .04em; }",
    "    .ds-box .ds-v { font-size: 15px; font-weight: 800; color: #1d4f7c; margin-top: 3px; }",
    "    .ds-rows { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 24px; }",
    "    .ds-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px dotted #d1d5db; font-size: 11px; }",
    "    .ds-row .ds-k { color: #6b7280; }",
    "    .ds-row .ds-v { font-weight: 600; }",
    "    .ds-mono { font-family: 'Courier New', monospace; }",
    "    .ds-section h2 { font-size: 11px; color: #1d4f7c; font-weight: 700; border-bottom: 1px solid #1d4f7c; padding-bottom: 3px; margin: 0 0 8px 0; text-transform: uppercase; letter-spacing: .04em; }",
    "    .ds-qr { width: 92px; height: 92px; border: 1px solid #e5e7eb; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 9px; color: #6b7280; text-align: center; padding: 4px; }",
    "    .ds-evidence { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }",
    "    .ds-evidence figure { margin: 0; border: 1px solid #d1d5db; padding: 3px; text-align: center; }",
    "    .ds-evidence img { width: 100%; height: 110px; object-fit: cover; }",
    "    .ds-evidence figcaption { font-size: 8px; color: #6b7280; text-transform: uppercase; letter-spacing: .06em; padding-top: 3px; }",
    "    .ds-psid { border: 2px solid #1d4f7c; border-radius: 8px; padding: 14px; text-align: center; }",
    "    .ds-psid .ds-amount { font-size: 24px; font-weight: 900; color: #1d4f7c; margin: 6px 0; }",
    "    .ds-note { background: #fffbeb; border-left: 3px solid #b45309; padding: 10px 14px; font-size: 11px; color: #78350f; }",
    "    .ds-slips { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; border-top: 2px dashed #9ca3af; padding-top: 12px; }",
    "    .ds-slip { border: 1px solid #d1d5db; border-radius: 6px; padding: 10px; font-size: 10px; }",
    "    .ds-slip h3 { font-size: 10px; text-transform: uppercase; letter-spacing: .06em; margin: 0 0 6px 0; color: #374151; }",
    "    .ds-sign { display: flex; justify-content: space-between; margin-top: 26px; }",
    "    .ds-sign .ds-sig { text-align: center; }",
    "    .ds-sign .ds-line { border-top: 1px solid #1d4f7c; width: 170px; margin: 0 auto 4px; padding-top: 4px; font-size: 10px; color: #6b7280; }",
    "    .ds-footer { margin-top: 22px; border-top: 1px solid #d1d5db; padding-top: 10px; font-size: 9px; color: #6b7280; display: flex; justify-content: space-between; }",
    "    @media print { body { background: #FFFFFF; padding: 0; } .sheet { box-shadow: none; width: auto; min-height: auto; } }"
  ].join('\n');

  var SNIPPETS = {
    header: [
      '  <div class="ds-block ds-header">',
      '    <img src="{% static \'img/project_logo.png\' %}" alt="Safe City">',
      '    <div>',
      '      <h1>SAFE CITY | TRAFFIC ENFORCEMENT E-CHALLAN</h1>',
      '      <div class="ds-sub">Government of Pakistan &middot; Computer-generated notice &middot; Do not accept cash</div>',
      '    </div>',
      "    {% if challan.payment_status == 'PAID' %}",
      '    <span class="ds-stamp">PAID</span>',
      "    {% elif challan.is_overdue %}",
      '    <span class="ds-stamp" style="border-color:#b91c1c;color:#b91c1c;">OVERDUE</span>',
      '    {% endif %}',
      '  </div>'
    ].join('\n'),
    ticket_meta: [
      '  <div class="ds-block ds-grid3">',
      '    <div class="ds-box"><div class="ds-k">Ticket No.</div><div class="ds-v ds-mono">{{ challan.ticket_no }}</div></div>',
      '    <div class="ds-box"><div class="ds-k">Vehicle</div><div class="ds-v ds-mono">{{ challan.plate_number }}</div></div>',
      '    <div class="ds-box"><div class="ds-k">Fine</div><div class="ds-v">PKR {{ challan.fine_amount|floatformat:0|intcomma }}</div></div>',
      '  </div>',
      '  <div class="ds-block ds-rows">',
      '    <div class="ds-row"><span class="ds-k">Violation</span><span class="ds-v">{{ challan.get_violation_type_display|default:challan.violation_type }}</span></div>',
      "    <div class=\"ds-row\"><span class=\"ds-k\">Location</span><span class=\"ds-v\">{{ challan.location|default:'-' }}</span></div>",
      "    <div class=\"ds-row\"><span class=\"ds-k\">Issued</span><span class=\"ds-v\">{{ challan.issue_date|date:'d M Y' }}</span></div>",
      "    <div class=\"ds-row\"><span class=\"ds-k\">Due</span><span class=\"ds-v\">{{ challan.due_date|date:'d M Y' }}</span></div>",
      "    <div class=\"ds-row\"><span class=\"ds-k\">Camera</span><span class=\"ds-v\">{{ challan.camera.camera_id|default:'-' }}</span></div>",
      '    <div class="ds-row"><span class="ds-k">Status</span><span class="ds-v">{{ challan.get_payment_status_display|default:challan.payment_status }}</span></div>',
      '  </div>'
    ].join('\n'),
    offender: [
      '  <div class="ds-block ds-section">',
      '    <h2>Offender Information</h2>',
      '    <div class="ds-rows">',
      "      <div class=\"ds-row\"><span class=\"ds-k\">Name</span><span class=\"ds-v\">{{ challan.owner_name|default:'-' }}</span></div>",
      "      <div class=\"ds-row\"><span class=\"ds-k\">CNIC</span><span class=\"ds-v ds-mono\">{{ challan.cnic|default:'-' }}</span></div>",
      "      <div class=\"ds-row\"><span class=\"ds-k\">Phone</span><span class=\"ds-v\">{{ challan.phone|default:'-' }}</span></div>",
      "      <div class=\"ds-row\"><span class=\"ds-k\">Address</span><span class=\"ds-v\">{{ challan.address|default:'-' }}</span></div>",
      '    </div>',
      '  </div>'
    ].join('\n'),
    vehicle: [
      '  <div class="ds-block ds-section">',
      '    <h2>Vehicle Information</h2>',
      '    <div class="ds-rows">',
      "      <div class=\"ds-row\"><span class=\"ds-k\">Type</span><span class=\"ds-v\">{{ challan.vehicle_type|default:'Car' }}</span></div>",
      "      <div class=\"ds-row\"><span class=\"ds-k\">Year</span><span class=\"ds-v\">{{ challan.make_year|default:'-' }}</span></div>",
      "      <div class=\"ds-row\"><span class=\"ds-k\">Color</span><span class=\"ds-v\">{{ challan.color|default:'-' }}</span></div>",
      "      <div class=\"ds-row\"><span class=\"ds-k\">Chassis</span><span class=\"ds-v ds-mono\">{{ challan.chassis_no|default:'-' }}</span></div>",
      '    </div>',
      '  </div>'
    ].join('\n'),
    evidence: [
      '  <div class="ds-block ds-section">',
      '    <h2>Violation Evidence</h2>',
      "    {% if challan.detection and challan.detection.raw_image %}",
      '    <div class="ds-evidence">',
      '      <figure>',
      '        <img src="{{ challan.detection.raw_image.url }}" alt="Violation frame">',
      '        <figcaption>Wide angle &middot; {{ challan.detection.camera.camera_id|default:"-" }}</figcaption>',
      '      </figure>',
      '      <figure>',
      '        <img src="{{ challan.detection.raw_image.url }}" alt="Plate crop">',
      '        <figcaption>Plate &middot; {{ challan.detection.effective_plate|default:"-" }}</figcaption>',
      '      </figure>',
      '    </div>',
      "    <div class=\"ds-row\" style=\"margin-top:8px;\"><span class=\"ds-k\">Captured</span><span class=\"ds-v\">{{ challan.detection.created_at|date:'d M Y H:i:s' }}</span></div>",
      '    {% else %}',
      '    <p style="font-size:10px;color:#6b7280;">No evidence image attached to this challan.</p>',
      '    {% endif %}',
      '  </div>'
    ].join('\n'),
    psid: [
      '  <div class="ds-block">',
      '    <div class="ds-grid3">',
      '      <div class="ds-box"><div class="ds-k">PSID</div><div class="ds-v ds-mono">{{ challan.psid }}</div></div>',
      '      <div class="ds-box"><div class="ds-k">Amount Due</div><div class="ds-v">PKR {{ challan.fine_amount|floatformat:0|intcomma }}</div></div>',
      '      <div class="ds-box"><div class="ds-k">Pay Before</div><div class="ds-v">{{ challan.due_date|date:"d M Y" }}</div></div>',
      '    </div>',
      '    <div class="ds-psid" style="margin-top:12px;">',
      '      <div class="ds-k" style="font-size:9px;color:#6b7280;text-transform:uppercase;letter-spacing:.04em;">Payment Service ID - quote at any bank, post office or mobile wallet</div>',
      '      <div class="ds-amount">PKR {{ challan.fine_amount|floatformat:0|intcomma }}</div>',
      '      <div class="ds-mono" style="font-size:12px;">{{ challan.psid }}</div>',
      '    </div>',
      '  </div>'
    ].join('\n'),
    instructions: [
      '  <div class="ds-block ds-note">',
      '    <b>Section 99-A, Motor Vehicles Ordinance 1965.</b> This e-challan is issued on the record of the Safe City',
      '    automated traffic enforcement system. The fine must be paid before <b>{{ challan.due_date|date:"d M Y" }}</b>.',
      '    Non-payment may lead to additional penalty, licence action or vehicle registration hold.',
      '    Appeals can be filed from the citizen portal within the statutory period.',
      '  </div>'
    ].join('\n'),
    slips: [
      '  <div class="ds-block">',
      '    <div class="ds-slips">',
      '      <div class="ds-slip">',
      '        <h3>Motorist Copy</h3>',
      '        <div class="ds-mono">Ticket: {{ challan.ticket_no }} &middot; Plate: {{ challan.plate_number }}</div>',
      '        <div>Violation: {{ challan.get_violation_type_display|default:challan.violation_type }}</div>',
      '        <div>Amount: PKR {{ challan.fine_amount|floatformat:0|intcomma }} &middot; Due: {{ challan.due_date|date:"d M Y" }}</div>',
      '      </div>',
      '      <div class="ds-slip">',
      '        <h3>Bank / Post Office Copy</h3>',
      '        <div class="ds-mono">PSID: {{ challan.psid }}</div>',
      '        <div>Head: C0263A &middot; Amount: PKR {{ challan.fine_amount|floatformat:0|intcomma }}</div>',
      '        <div style="margin-top:8px;border-top:1px dashed #9ca3af;padding-top:6px;">Teller stamp &amp; signature</div>',
      '      </div>',
      '    </div>',
      '  </div>'
    ].join('\n'),
    footer: [
      '  <div class="ds-sign">',
      '    <div class="ds-sig">',
      '      <div class="ds-line">{{ officer_signature_name|default:"Issuing Officer" }}</div>',
      '      <div style="font-size:9px;color:#6b7280;">{{ officer_signature_designation|default:"Traffic Enforcement" }}</div>',
      '    </div>',
      '    <div class="ds-sig">',
      '      <div class="ds-line">SAFE CITY FYP</div>',
      '      <div style="font-size:9px;color:#6b7280;">System-generated document</div>',
      '    </div>',
      '  </div>',
      '  <div class="ds-footer">',
      '    <span>Generated {{ challan.issue_date|date:"d M Y" }} &middot; {{ challan.ticket_no }}</span>',
      '    <span>Safe City Automated Traffic Enforcement &middot; verifiable via citizen portal</span>',
      '  </div>'
    ].join('\n')
  };

  var MIN_CHARS = 50;

  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function Designer(root) {
    this.canvas = qs('[data-ds-canvas]', root);
    this.palette = qs('[data-ds-palette]', root);
    this.form = qs('[data-ds-form]', root);
    this.html = qs('[data-ds-html]', root);
    this.counter = qs('[data-ds-counter]', root);
    this.blocksList = qs('[data-ds-blocks-list]', root);
    this.countBadge = qs('[data-ds-count]', root);
    this.generateBtn = qs('[data-ds-generate]', root);
    this.clearBtn = qs('[data-ds-clear]', root);
    this.dragSrc = null;
    this.emptyNode = null;
    this.bind();
    this.sync();
  }

  Designer.prototype.placeholder = function () {
    if (!this.emptyNode) {
      this.emptyNode = document.createElement('div');
      this.emptyNode.className = 'it-ds-empty';
      this.emptyNode.setAttribute('data-ds-empty', '');
      this.emptyNode.innerHTML = '<i class="bi bi-arrows-move"></i>' +
        '<p class="mb-1">Drop blocks here to build the layout</p>' +
        '<p class="sc-hint mb-0">The canvas is a single A4 sheet - blocks stack top to bottom.</p>';
    }
    return this.emptyNode;
  };

  Designer.prototype.placed = function () {
    return qsa('.it-ds-placed', this.canvas);
  };

  Designer.prototype.addBlock = function (id, label) {
    if (!SNIPPETS.hasOwnProperty(id)) { return; }
    if (this.emptyNode && this.emptyNode.parentNode) { this.canvas.removeChild(this.emptyNode); }
    var pal = qs('.it-ds-pal-item[data-block="' + id + '"]', this.palette);
    var icon = pal ? pal.querySelector('.it-ds-pal-ic') : null;
    var iconClass = icon ? icon.className.replace('it-ds-pal-ic', '').trim() : 'bi bi-card-text';
    var item = document.createElement('div');
    item.className = 'it-ds-placed';
    item.draggable = true;
    item.setAttribute('data-block', id);
    item.innerHTML =
      '<i class="' + iconClass + ' it-ds-placed-ic"></i>' +
      '<div class="it-ds-placed-body"><div class="it-ds-placed-name">' + label + '</div>' +
      '<div class="it-ds-placed-pos"></div></div>' +
      '<button type="button" class="it-ds-placed-x" title="Remove block" aria-label="Remove block"><i class="bi bi-x-lg"></i></button>';
    var self = this;
    item.addEventListener('dragstart', function (evt) {
      self.dragSrc = item;
      item.classList.add('it-dragging');
      try { evt.dataTransfer.setData('text/plain', 'move'); } catch (e) {}
      evt.dataTransfer.effectAllowed = 'move';
    });
    item.addEventListener('dragend', function () {
      self.dragSrc = null;
      item.classList.remove('it-dragging');
    });
    item.querySelector('.it-ds-placed-x').addEventListener('click', function () {
      if (item.parentNode) { item.parentNode.removeChild(item); }
      self.sync();
    });
    this.canvas.appendChild(item);
    this.sync();
  };

  Designer.prototype.buildHtml = function () {
    var ids = this.placed().map(function (el) { return el.getAttribute('data-block'); });
    var body = ids.map(function (id) { return SNIPPETS[id] || ''; }).filter(Boolean).join('\n\n');
    return '{% load static %}\n{% load humanize %}\n<!DOCTYPE html>\n<html lang="en">\n<head>\n' +
      '<meta charset="UTF-8">\n<title>E-Challan {{ challan.ticket_no }}</title>\n<style>\n' +
      DS_STYLES + '\n</style>\n</head>\n<body>\n<div class="sheet">\n\n' +
      (body || '<!-- no blocks placed -->') + '\n\n</div>\n</body>\n</html>';
  };

  Designer.prototype.generate = function () {
    if (!this.placed().length) {
      window.alert('Place at least one block on the canvas first.');
      return false;
    }
    this.html.value = this.buildHtml();
    this.sync();
    return true;
  };

  Designer.prototype.sync = function () {
    var placed = this.placed();
    var labels = [];
    placed.forEach(function (el, idx) {
      var pos = el.querySelector('.it-ds-placed-pos');
      if (pos) { pos.textContent = 'position ' + (idx + 1) + ' &middot; ' + el.getAttribute('data-block'); }
      labels.push(el.querySelector('.it-ds-placed-name').textContent);
    });
    if (!placed.length && this.emptyNode) { this.canvas.appendChild(this.placeholder()); }
    if (this.countBadge) { this.countBadge.textContent = placed.length + (placed.length === 1 ? ' block' : ' blocks'); }
    if (this.blocksList) {
      this.blocksList.textContent = labels.length ? labels.join(' > ') : 'no blocks placed';
    }
    if (this.counter) {
      var n = (this.html.value || '').length;
      this.counter.innerHTML = n + ' characters &middot; ' + (n >= MIN_CHARS ? 'ready to save' : 'at least ' + MIN_CHARS + ' required');
    }
  };

  Designer.prototype.bind = function () {
    var self = this;

    qsa('.it-ds-pal-item', this.palette).forEach(function (pal) {
      pal.addEventListener('dragstart', function (evt) {
        self.dragSrc = null;
        try { evt.dataTransfer.setData('text/plain', 'add:' + pal.getAttribute('data-block')); } catch (e) {}
        evt.dataTransfer.effectAllowed = 'copy';
      });
      pal.addEventListener('click', function () {
        self.addBlock(pal.getAttribute('data-block'), pal.getAttribute('data-label'));
      });
    });

    this.canvas.addEventListener('dragover', function (evt) {
      evt.preventDefault();
      self.canvas.classList.add('it-drag-over');
      if (!self.dragSrc) { return; }
      var target = null;
      qsa('.it-ds-placed', self.canvas).forEach(function (el) {
        if (el === self.dragSrc) { return; }
        var box = el.getBoundingClientRect();
        if (evt.clientY < box.top + box.height / 2) { target = el; }
      });
      if (target) {
        self.canvas.insertBefore(self.dragSrc, target);
      } else {
        self.canvas.appendChild(self.dragSrc);
      }
    });

    this.canvas.addEventListener('dragleave', function () {
      self.canvas.classList.remove('it-drag-over');
    });

    this.canvas.addEventListener('drop', function (evt) {
      evt.preventDefault();
      self.canvas.classList.remove('it-drag-over');
      var data = '';
      try { data = evt.dataTransfer.getData('text/plain') || ''; } catch (e) {}
      if (!self.dragSrc && data.indexOf('add:') === 0) {
        var id = data.slice(4);
        var pal = qs('.it-ds-pal-item[data-block="' + id + '"]', self.palette);
        self.addBlock(id, pal ? pal.getAttribute('data-label') : id);
      }
      self.dragSrc = null;
      self.sync();
    });

    if (this.generateBtn) {
      this.generateBtn.addEventListener('click', function () { self.generate(); });
    }

    if (this.clearBtn) {
      this.clearBtn.addEventListener('click', function () {
        qsa('.it-ds-placed', self.canvas).forEach(function (el) { el.parentNode.removeChild(el); });
        self.sync();
      });
    }

    if (this.html) {
      this.html.addEventListener('input', function () { self.sync(); });
    }

    if (this.form) {
      this.form.addEventListener('submit', function (evt) {
        var value = (self.html.value || '').trim();
        if (value.length < MIN_CHARS) {
          evt.preventDefault();
          if (self.placed().length) {
            self.generate();
            if ((self.html.value || '').trim().length >= MIN_CHARS) { return; }
          }
          window.alert('The template HTML needs at least ' + MIN_CHARS + ' characters. Generate it from the canvas first.');
          self.html.focus();
        }
      });
    }
  };

  function init() {
    var root = document;
    if (!qs('[data-ds-canvas]', root)) { return; }
    new Designer(root);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
