(function () {
  /* ── Estilos do dropdown ── */
  var estilo = document.createElement('style');
  estilo.textContent =
    '.ac-dropdown{' +
      'position:absolute;top:calc(100% + 4px);left:0;right:0;' +
      'background:#fff;border:1.5px solid #1B4F72;border-radius:10px;' +
      'box-shadow:0 8px 24px rgba(27,79,114,0.18);' +
      'z-index:300;overflow:hidden;max-height:300px;overflow-y:auto;' +
    '}' +
    '.ac-item{' +
      'display:flex;align-items:center;justify-content:space-between;' +
      'padding:11px 14px;cursor:pointer;min-height:44px;' +
      'border-bottom:1px solid #eef2f7;transition:background 0.12s;' +
      '-webkit-tap-highlight-color:transparent;' +
    '}' +
    '.ac-item:last-child{border-bottom:none;}' +
    '.ac-item:hover,.ac-item-activo{background:#D6E8F5;}' +
    '.ac-nome{font-weight:600;color:#0d2137;font-size:0.9rem;}' +
    '.ac-nome strong{font-weight:800;color:#1B4F72;}' +
    '.ac-municipio{font-size:0.78rem;color:#6b7a8d;white-space:nowrap;margin-left:8px;overflow:hidden;text-overflow:ellipsis;max-width:45%;}' +
    '.ac-municipio strong{font-weight:700;color:#1B4F72;}';
  document.head.appendChild(estilo);

  /* ── Utilitários ── */
  function normalizar(str) {
    return str.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  function escHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /* Envolve em <strong> as partes de `original` que coincidem com os tokens.
     Usa as posições do texto normalizado (mesmo comprimento que o original
     para caracteres portugueses), preservando maiúsculas e acentos no output. */
  function destacar(original, tokens) {
    if (!tokens.length) return escHtml(original);
    var norm = normalizar(original);
    /* recolhe todos os intervalos [inicio, fim) */
    var ranges = [];
    tokens.forEach(function (t) {
      var pos = 0;
      while (pos < norm.length) {
        var idx = norm.indexOf(t, pos);
        if (idx === -1) break;
        ranges.push([idx, idx + t.length]);
        pos = idx + 1;
      }
    });
    if (!ranges.length) return escHtml(original);
    /* ordena e funde intervalos sobrepostos */
    ranges.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [ranges[0].slice()];
    for (var i = 1; i < ranges.length; i++) {
      var last = merged[merged.length - 1];
      if (ranges[i][0] < last[1]) {
        last[1] = Math.max(last[1], ranges[i][1]);
      } else {
        merged.push(ranges[i].slice());
      }
    }
    /* reconstrói o HTML intercalando <strong> */
    var html = '';
    var cursor = 0;
    merged.forEach(function (r) {
      html += escHtml(original.slice(cursor, r[0]));
      html += '<strong>' + escHtml(original.slice(r[0], r[1])) + '</strong>';
      cursor = r[1];
    });
    html += escHtml(original.slice(cursor));
    return html;
  }

  /* Devolve { itens, tokens } para que renderizar possa destacar os matches */
  function filtrar(query) {
    if (!window.FREGUESIAS || !FREGUESIAS.length) return { itens: [], tokens: [] };
    var tokens = normalizar(query.trim()).split(/\s+/).filter(function (t) { return t.length >= 2; });
    if (!tokens.length) return { itens: [], tokens: [] };
    var itens = FREGUESIAS.filter(function (f) {
      var texto = normalizar(f.nome) + ' ' + normalizar(f.municipio);
      return tokens.every(function (t) { return texto.indexOf(t) !== -1; });
    }).slice(0, 8);
    return { itens: itens, tokens: tokens };
  }

  /* ── Função principal ── */
  window.iniciarAutocomplete = function (inputEl, opcoes) {
    if (!inputEl) return;
    opcoes = opcoes || {};

    var wrapper = inputEl.parentElement;
    if (getComputedStyle(wrapper).position === 'static') {
      wrapper.style.position = 'relative';
    }

    var dropdown = document.createElement('div');
    dropdown.className = 'ac-dropdown';
    dropdown.setAttribute('role', 'listbox');
    dropdown.style.display = 'none';
    wrapper.appendChild(dropdown);

    var resultados = [];
    var idxActivo = -1;

    function renderizar(lista, tokens) {
      resultados = lista;
      idxActivo = -1;
      dropdown.innerHTML = lista.map(function (f, i) {
        return '<div class="ac-item" role="option" data-idx="' + i + '">' +
          '<span class="ac-nome">' + destacar(f.nome, tokens) + '</span>' +
          '<span class="ac-municipio">' + destacar(f.municipio, tokens) + '</span>' +
          '</div>';
      }).join('');
      dropdown.style.display = 'block';

      dropdown.querySelectorAll('.ac-item').forEach(function (item) {
        /* desktop: mousedown evita blur no input antes do click */
        item.addEventListener('mousedown', function (e) {
          e.preventDefault();
          selecionar(parseInt(this.getAttribute('data-idx')));
        });
        /* mobile: touchend com preventDefault evita o delay de 300ms */
        item.addEventListener('touchend', function (e) {
          e.preventDefault();
          selecionar(parseInt(this.getAttribute('data-idx')));
        });
      });
    }

    function fechar() {
      dropdown.style.display = 'none';
      resultados = [];
      idxActivo = -1;
    }

    function selecionar(idx) {
      var f = resultados[idx];
      if (!f) return;
      inputEl.value = f.nome;
      fechar();
      if (opcoes.aoSelecionar) opcoes.aoSelecionar(f);
    }

    function realcar(idx) {
      dropdown.querySelectorAll('.ac-item').forEach(function (item, i) {
        item.classList.toggle('ac-item-activo', i === idx);
      });
    }

    /* ── Eventos ── */
    inputEl.addEventListener('input', function () {
      var r = filtrar(this.value);
      if (r.itens.length) renderizar(r.itens, r.tokens);
      else fechar();
    });

    inputEl.addEventListener('keydown', function (e) {
      var n = resultados.length;
      if (!n) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        idxActivo = Math.min(idxActivo + 1, n - 1);
        realcar(idxActivo);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        idxActivo = Math.max(idxActivo - 1, -1);
        realcar(idxActivo);
      } else if (e.key === 'Enter' && idxActivo >= 0) {
        e.preventDefault();
        selecionar(idxActivo);
      } else if (e.key === 'Escape') {
        fechar();
      }
    });

    /* Fecha ao perder foco — delay para deixar o mousedown/touchend correr primeiro */
    inputEl.addEventListener('blur', function () {
      setTimeout(fechar, 150);
    });

    /* Fecha ao clicar fora */
    document.addEventListener('click', function (e) {
      if (!wrapper.contains(e.target)) fechar();
    });
  };
})();
