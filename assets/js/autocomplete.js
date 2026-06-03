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
    '.ac-municipio{font-size:0.78rem;color:#6b7a8d;white-space:nowrap;margin-left:8px;overflow:hidden;text-overflow:ellipsis;max-width:45%;}';
  document.head.appendChild(estilo);

  /* ── Utilitários ── */
  function normalizar(str) {
    return str.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  function escHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function filtrar(query) {
    if (!window.FREGUESIAS || !FREGUESIAS.length) return [];
    var q = normalizar(query.trim());
    if (q.length < 2) return [];
    return FREGUESIAS.filter(function (f) {
      return normalizar(f.nome).indexOf(q) !== -1 ||
             normalizar(f.municipio).indexOf(q) !== -1;
    }).slice(0, 8);
  }

  /* ── Função principal ── */
  window.iniciarAutocomplete = function (inputEl, opcoes) {
    if (!inputEl) return;
    opcoes = opcoes || {};

    var wrapper = inputEl.parentElement;
    /* garante que o wrapper é o âncora de posicionamento */
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

    function renderizar(lista) {
      resultados = lista;
      idxActivo = -1;
      dropdown.innerHTML = lista.map(function (f, i) {
        return '<div class="ac-item" role="option" data-idx="' + i + '">' +
          '<span class="ac-nome">' + escHtml(f.nome) + '</span>' +
          '<span class="ac-municipio">' + escHtml(f.municipio) + '</span>' +
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
      var lista = filtrar(this.value);
      if (lista.length) renderizar(lista);
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
