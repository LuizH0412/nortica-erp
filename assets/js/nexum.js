/* Comportamentos comuns das telas do Nexum (máscaras, abas, endereço, listas). */
(function () {
  var Nexum = (window.Nexum = window.Nexum || {});

  function el(id) { return document.getElementById(id); }

  // ---------- Máscaras (campos com data-mascara) ----------
  var PADROES = {
    cpf: "XXX.XXX.XXX-XX", cnpj: "XX.XXX.XXX/XXXX-XX", cep: "XXXXX-XXX",
    fixo: "(XX) XXXX-XXXX", celular: "(XX) XXXXX-XXXX"
  };
  function aplicar(valor, padrao) {
    var saida = "", i = 0;
    for (var k = 0; k < padrao.length; k++) {
      if (i >= valor.length) break;
      saida += padrao[k] === "X" ? valor[i++] : padrao[k];
    }
    return saida;
  }
  function formatar(campo) {
    var tipo = campo.dataset.mascara, v = campo.value;
    if (tipo === "documento") {
      v = v.toUpperCase().replace(/[^0-9A-Z]/g, "").slice(0, 14);
      campo.value = aplicar(v, (v.length <= 11 && /^\d*$/.test(v)) ? PADROES.cpf : PADROES.cnpj);
    } else if (tipo === "cnpj") {
      campo.value = aplicar(v.toUpperCase().replace(/[^0-9A-Z]/g, "").slice(0, 14), PADROES.cnpj);
    } else if (tipo === "cpf") {
      campo.value = aplicar(v.replace(/\D/g, "").slice(0, 11), PADROES.cpf);
    } else if (tipo === "cep") {
      campo.value = aplicar(v.replace(/\D/g, "").slice(0, 8), PADROES.cep);
    } else if (tipo === "numeros") {
      campo.value = v.replace(/\D/g, "");
    } else if (tipo === "fone") {
      // Telefone sem DDD: 9999-9999 (fixo) ou 99999-9999 (celular)
      v = v.replace(/\D/g, "").slice(0, 9);
      campo.value = v.length > 8 ? aplicar(v, "XXXXX-XXXX") : aplicar(v, "XXXX-XXXX");
    } else if (tipo === "telefone") {
      v = v.replace(/\D/g, "").slice(0, 11);
      campo.value = aplicar(v, v.length > 10 ? PADROES.celular : PADROES.fixo);
    }
  }
  Nexum.mascaras = function () {
    document.querySelectorAll("[data-mascara]").forEach(formatar);
    document.addEventListener("input", function (e) {
      if (e.target.dataset && e.target.dataset.mascara) formatar(e.target);
    });
  };

  // ---------- Abas (botões data-aba + painéis data-painel) ----------
  // Abre a primeira aba que tiver erro e marca com um ponto vermelho as que têm.
  Nexum.abas = function () {
    var abas = document.querySelectorAll("[data-aba]");
    var paineis = document.querySelectorAll("[data-painel]");
    function mostrar(nome) {
      abas.forEach(function (b) {
        var ativa = b.dataset.aba === nome;
        b.classList.toggle("aba-ativa", ativa);
        b.setAttribute("aria-selected", ativa ? "true" : "false");
      });
      paineis.forEach(function (p) { p.classList.toggle("hidden", p.dataset.painel !== nome); });
    }
    abas.forEach(function (b) {
      b.addEventListener("click", function () { mostrar(b.dataset.aba); });
    });
    var primeiraComErro = null;
    paineis.forEach(function (p) {
      if (p.querySelector("[data-erro]")) {
        var ponto = document.querySelector('[data-aba="' + p.dataset.painel + '"] [data-ponto]');
        if (ponto) ponto.classList.remove("hidden");
        primeiraComErro = primeiraComErro || p.dataset.painel;
      }
    });
    // Sem erro, abre a aba indicada no endereço (ex.: ...#usuario) ou a primeira
    var doEndereco = location.hash.slice(1);
    var existe = doEndereco && document.querySelector('[data-aba="' + doEndereco + '"]');
    mostrar(primeiraComErro || (existe ? doEndereco : abas[0] && abas[0].dataset.aba));
    return mostrar;
  };

  // ---------- Aviso (mensagem acima do formulário) ----------
  var ESTILOS = {
    info: "bg-primary-soft text-primary-text border border-line",
    sucesso: "bg-success/10 text-success border border-success/30",
    erro: "bg-danger-soft text-danger border border-danger/20"
  };
  Nexum.aviso = function (id) {
    var aviso = el(id);
    return function (mensagem, tipo) {
      if (!mensagem) { aviso.className = "hidden"; aviso.textContent = ""; return; }
      aviso.className = "rounded-lg px-3 py-2 text-sm " + ESTILOS[tipo || "info"];
      aviso.textContent = mensagem;
    };
  };

  // ---------- Consulta JSON ({ok, dados} ou {ok: false, mensagem}) ----------
  Nexum.consultar = function (url, botao, avisar, aoConcluir) {
    avisar("Consultando...", "info");
    botao.disabled = true;
    fetch(url)
      .then(function (r) { return r.json(); })
      .then(function (r) {
        if (!r.ok) { avisar(r.mensagem, "erro"); return; }
        aoConcluir(r.dados);
      })
      .catch(function () {
        avisar("Não conseguimos falar com o servidor agora. Tente de novo em instantes ou preencha os dados manualmente.", "erro");
      })
      .finally(function () { botao.disabled = false; });
  };

  // O que a consulta trouxer substitui o que estava digitado; vazio não apaga nada.
  Nexum.preencher = function (id, valor) {
    if (!valor) return;
    var campo = el(id);
    campo.value = valor;
    campo.dispatchEvent(new Event("input", { bubbles: true }));
  };

  // ---------- Endereço: cidade com busca + consulta de CEP ----------
  // Usa, por padrão, os ids: id_uf, cidade_busca, id_municipio, cidade_opcoes, id_cep,
  // btn-buscar-cep, id_logradouro, id_bairro.
  // Para um segundo endereço na mesma página (ex.: janela com prefixo "end"), passe
  // opcoes.ids = Nexum.idsEndereco("end").
  Nexum.idsEndereco = function (prefixo) {
    var p = prefixo ? prefixo + "-" : "";
    return {
      uf: "id_" + p + "uf", busca: p + "cidade_busca", municipio: "id_" + p + "municipio",
      lista: p + "cidade_opcoes", cep: "id_" + p + "cep", botaoCep: p + "btn-buscar-cep",
      logradouro: "id_" + p + "logradouro", bairro: "id_" + p + "bairro"
    };
  };
  Nexum.endereco = function (opcoes) {
    var avisar = opcoes.avisar;
    var ids = opcoes.ids || Nexum.idsEndereco("");
    var uf = el(ids.uf), busca = el(ids.busca), oculto = el(ids.municipio);
    var lista = el(ids.lista), timer = null;

    function fechar() { lista.classList.add("hidden"); lista.innerHTML = ""; }
    function escolher(m) { oculto.value = m.id; busca.value = m.nome; uf.value = m.uf; fechar(); }
    function mostrarOpcoes(itens) {
      lista.innerHTML = "";
      if (!itens.length) {
        var vazio = document.createElement("li");
        vazio.className = "px-3 py-2 text-sm text-ink-soft";
        vazio.textContent = "Nenhuma cidade encontrada.";
        lista.appendChild(vazio);
      }
      itens.forEach(function (m) {
        var li = document.createElement("li");
        li.className = "px-3 py-2 text-sm cursor-pointer hover:bg-primary-soft";
        li.textContent = m.nome + " - " + m.uf;
        li.addEventListener("mousedown", function (e) { e.preventDefault(); escolher(m); });
        lista.appendChild(li);
      });
      lista.classList.remove("hidden");
    }
    busca.addEventListener("input", function () {
      oculto.value = "";
      clearTimeout(timer);
      var q = busca.value.trim();
      if (q.length < 2) { fechar(); return; }
      timer = setTimeout(function () {
        fetch(opcoes.urlCidades + "?uf=" + encodeURIComponent(uf.value) + "&q=" + encodeURIComponent(q))
          .then(function (r) { return r.json(); })
          .then(function (r) { mostrarOpcoes(r.resultados); })
          .catch(fechar);
      }, 250);
    });
    busca.addEventListener("blur", function () { setTimeout(fechar, 150); });
    uf.addEventListener("change", function () { oculto.value = ""; busca.value = ""; fechar(); });

    // Cidade digitada mas não escolhida na lista: não deixa salvar
    opcoes.form.addEventListener("submit", function (e) {
      if (busca.value.trim() && !oculto.value) {
        e.preventDefault();
        if (opcoes.mostrarAba) opcoes.mostrarAba(opcoes.abaEndereco);
        avisar("Escolha a cidade na lista de opções que aparece enquanto você digita.", "erro");
        busca.focus();
      }
    });

    function aplicarMunicipio(m) {
      if (!m) return false;
      uf.value = m.uf; oculto.value = m.id; busca.value = m.nome;
      return true;
    }

    el(ids.botaoCep).addEventListener("click", function () {
      Nexum.consultar(opcoes.urlCep + "?cep=" + encodeURIComponent(el(ids.cep).value), this, avisar, function (d) {
        Nexum.preencher(ids.logradouro, d.logradouro);
        Nexum.preencher(ids.bairro, d.bairro);
        if (aplicarMunicipio(d.municipio)) {
          avisar("Endereço preenchido pelo CEP. Falta só conferir o número e o complemento.", "sucesso");
        } else {
          if (d.uf) uf.value = d.uf;
          oculto.value = ""; busca.value = "";
          avisar("Endereço preenchido, mas não conseguimos identificar a cidade. Escolha a cidade na lista.", "info");
        }
      });
    });

    // Limpa a cidade (usado ao reabrir uma janela de endereço)
    function limparMunicipio() { uf.value = ""; oculto.value = ""; busca.value = ""; fechar(); }

    return { aplicarMunicipio: aplicarMunicipio, limparMunicipio: limparMunicipio };
  };

  // ---------- Listas: selecionar registros e "selecionar todos" ----------
  Nexum.selecao = function () {
    var todos = document.querySelector("[data-selecionar-todos]");
    var itens = Array.prototype.slice.call(document.querySelectorAll("[data-selecionar]"));
    if (!todos) return;
    if (!itens.length) { todos.disabled = true; return; }
    todos.addEventListener("change", function () {
      itens.forEach(function (c) { c.checked = todos.checked; });
    });
    // O "selecionar todos" acompanha: cheio, vazio ou parcial (traço)
    itens.forEach(function (c) {
      c.addEventListener("change", function () {
        var marcados = itens.filter(function (i) { return i.checked; }).length;
        todos.checked = marcados === itens.length;
        todos.indeterminate = marcados > 0 && marcados < itens.length;
      });
    });
  };

  // ---------- Menu lateral: grupos (<details data-menu>) abrem e fecham com animação ----------
  // Grupos com o mesmo data-grupo funcionam como sanfona: abrir um fecha os outros.
  Nexum.menu = function () {
    var reduzir = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var ABRIR = { duration: 260, easing: "cubic-bezier(.2,.8,.2,1)" };
    var FECHAR = { duration: 200, easing: "cubic-bezier(.4,0,1,1)" };

    function conteudo(d) { return d.querySelector(":scope > [data-menu-conteudo]"); }

    function animar(d, abrir) {
      var c = conteudo(d);
      if (d._animacao) d._animacao.cancel();
      if (reduzir) { d.open = abrir; return; }
      c.style.overflow = "hidden";
      if (abrir) d.open = true;
      var altura = c.scrollHeight + "px";
      var quadros = abrir
        ? [{ height: "0px", opacity: 0, transform: "translateY(-4px)" }, { height: altura, opacity: 1, transform: "none" }]
        : [{ height: altura, opacity: 1, transform: "none" }, { height: "0px", opacity: 0, transform: "translateY(-4px)" }];
      var a = c.animate(quadros, abrir ? ABRIR : FECHAR);
      d._animacao = a;
      a.onfinish = function () {
        if (!abrir) d.open = false;
        c.style.overflow = "";
        d._animacao = null;
      };
      a.oncancel = function () { c.style.overflow = ""; };
    }

    document.querySelectorAll("details[data-menu]").forEach(function (d) {
      var resumo = d.querySelector(":scope > summary");
      resumo.addEventListener("click", function (e) {
        e.preventDefault();
        var abrir = !d.open || (d._animacao && !d._abrindo);
        d._abrindo = abrir;
        if (abrir && d.dataset.grupo) {
          document.querySelectorAll('details[data-menu][data-grupo="' + d.dataset.grupo + '"]').forEach(function (outro) {
            if (outro !== d && outro.open) animar(outro, false);
          });
        }
        animar(d, abrir);
      });
    });
  };

  // ---------- Gerenciador de cadastros simples (função, setor, tipo de cliente, TAG...) ----------
  // Abre pelo botão com data-gerenciar (veja partials/botao_gerenciar.html e gerenciador_cadastro.html).
  // Pesquisa, cadastra, renomeia, ativa/desativa e exclui; mantém o campo do formulário em dia.
  // O campo (data-alvo) pode ser um <select> ou um grupo de pílulas (<div data-pilulas>) para marcar vários.
  Nexum.gerenciador = function (csrf) {
    var dialogo = el("gerenciador");
    if (!dialogo) return;
    var titulo = el("gerenciador-titulo"), busca = el("gerenciador-busca"), lista = el("gerenciador-lista");
    var novo = el("gerenciador-novo"), adicionar = el("gerenciador-adicionar"), aviso = el("gerenciador-aviso");
    var cfg = null, timer = null;

    function urlDo(modelo, id) { return modelo.replace("/0/", "/" + id + "/"); }
    function avisar(texto, tipo) {
      if (!texto) { aviso.className = "hidden"; return; }
      aviso.className = "rounded-lg px-3 py-2 text-sm " + ESTILOS[tipo || "info"];
      aviso.textContent = texto;
    }
    function enviar(url, dados) {
      var corpo = new FormData();
      Object.keys(dados || {}).forEach(function (k) { corpo.append(k, dados[k]); });
      return fetch(url, { method: "POST", body: corpo, headers: { "X-CSRFToken": csrf } })
        .then(function (r) { return r.json(); });
    }
    function falhou() { avisar("Não foi possível falar com o servidor. Tente de novo.", "erro"); }

    // Pílula (marcação múltipla, ex.: TAGs) — o mesmo visual de partials/pilulas.html
    function criarPilula(item, nomeCampo) {
      var rotulo = document.createElement("label");
      rotulo.className = "pilula";
      var caixa = document.createElement("input");
      caixa.type = "checkbox"; caixa.name = nomeCampo; caixa.value = String(item.id);
      var texto = document.createElement("span");
      texto.textContent = item.nome;
      rotulo.appendChild(caixa); rotulo.appendChild(texto);
      return rotulo;
    }
    function sincronizarPilulas(grupo, item, removido) {
      var caixa = grupo.querySelector('input[value="' + item.id + '"]');
      var pilula = caixa && caixa.closest("label");
      if (removido) { if (pilula) pilula.remove(); }
      else if (!item.ativo) { if (pilula && !caixa.checked) pilula.remove(); }  // quem já marcou continua vendo
      else if (pilula) pilula.querySelector("span").textContent = item.nome;
      else grupo.insertBefore(criarPilula(item, grupo.dataset.pilulas), grupo.querySelector("[data-vazio]"));
      var vazio = grupo.querySelector("[data-vazio]");
      if (vazio) vazio.classList.toggle("hidden", !!grupo.querySelector("label.pilula"));
    }
    function escolher(item) {
      var alvo = el(cfg.alvo);
      if (alvo.tagName === "SELECT") {
        alvo.value = String(item.id);
        alvo.dispatchEvent(new Event("change", { bubbles: true }));
        return;
      }
      var caixa = alvo.querySelector('input[value="' + item.id + '"]');
      if (caixa) caixa.checked = true;
    }

    // Mantém o campo do formulário igual ao cadastro
    function sincronizar(item, removido) {
      var select = el(cfg.alvo);
      if (select.tagName !== "SELECT") { sincronizarPilulas(select, item, removido); return; }
      var opcao = Array.prototype.find.call(select.options, function (o) { return o.value === String(item.id); });
      if (removido) {
        if (opcao) { if (opcao.selected) select.value = ""; opcao.remove(); }
        return;
      }
      if (!item.ativo) {
        if (opcao && !opcao.selected) opcao.remove();  // quem já usa continua vendo
        return;
      }
      if (opcao) opcao.textContent = item.nome;
      else select.add(new Option(item.nome, item.id));
    }

    // Cadastro que pertence a outro (ex.: subgrupo -> grupo): o valor do campo pai vai junto
    function valorPai() { return cfg.paiCampo ? el(cfg.paiCampo).value : ""; }

    function carregar() {
      fetch(cfg.urlLista + "?q=" + encodeURIComponent(busca.value.trim()) + "&pai=" + encodeURIComponent(valorPai()))
        .then(function (r) { return r.json(); })
        .then(function (r) { desenhar(r.itens); })
        .catch(falhou);
    }

    function botaoIcone(svg, rotulo, classe) {
      var b = document.createElement("button");
      b.type = "button"; b.title = rotulo; b.setAttribute("aria-label", rotulo);
      b.className = "rounded-md p-1.5 text-ink-soft transition " + classe;
      b.innerHTML = svg;
      return b;
    }
    var SVG = {
      lapis: '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.17 6.81a2.83 2.83 0 0 0-4-4L3.84 16.17a2 2 0 0 0-.5.83l-1.32 4.35a.5.5 0 0 0 .62.62l4.35-1.32a2 2 0 0 0 .83-.5z"/><path d="m15 5 4 4"/></svg>',
      lixeira: '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
      check: '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
      x: '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>'
    };

    function desenhar(itens) {
      lista.innerHTML = "";
      if (!itens.length) {
        var vazio = document.createElement("li");
        vazio.className = "px-4 py-6 text-center text-sm text-ink-soft";
        vazio.textContent = busca.value.trim() ? "Nada encontrado. Cadastre abaixo." : "Nada cadastrado ainda.";
        lista.appendChild(vazio);
        return;
      }
      itens.forEach(function (item) { lista.appendChild(linha(item)); });
    }

    function linha(item) {
      var li = document.createElement("li");
      li.className = "flex items-center gap-2 px-3 py-2 transition-colors hover:bg-primary-soft/50";

      // Nome: clicar usa no cadastro
      var nome = document.createElement("button");
      nome.type = "button";
      nome.className = "min-w-0 flex-1 truncate rounded-md px-1 py-1 text-left text-sm font-medium " +
        (item.ativo ? "hover:text-primary-text" : "text-ink-soft line-through decoration-ink-soft/40");
      nome.textContent = item.nome;
      nome.title = item.ativo ? "Usar " + item.nome : "Desativad" + cfg.artigo + ": ative para usar";
      nome.addEventListener("click", function () {
        if (!item.ativo) { avisar("Ative " + item.nome + " para poder usar.", "info"); return; }
        escolher(item);
        dialogo.close();
      });

      var uso = document.createElement("span");
      uso.className = "shrink-0 rounded-full bg-page px-2 py-0.5 text-xs text-ink-soft";
      uso.textContent = item.uso + " " + (cfg.usoCurto || "em uso");
      uso.title = "Em uso por " + item.uso + " " + (cfg.usoLongo || "registro(s)");

      // Interruptor ativo/desativado
      var chave = document.createElement("label");
      chave.className = "relative inline-flex shrink-0 cursor-pointer";
      chave.title = item.ativo ? "Ativ" + cfg.artigo + " (clique para desativar)" : "Desativad" + cfg.artigo + " (clique para ativar)";
      chave.innerHTML = '<input type="checkbox" class="peer sr-only"' + (item.ativo ? " checked" : "") + '>' +
        '<span class="h-5 w-9 rounded-full bg-line transition peer-checked:bg-primary peer-focus-visible:ring-2 peer-focus-visible:ring-primary/30"></span>' +
        '<span class="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition peer-checked:translate-x-4"></span>';
      chave.querySelector("input").addEventListener("change", function (e) {
        enviar(urlDo(cfg.urlSalvar, item.id), { ativo: e.target.checked ? "1" : "0" }).then(function (r) {
          if (!r.ok) { avisar(r.mensagem, "erro"); carregar(); return; }
          sincronizar(r.item);
          avisar(r.item.nome + (r.item.ativo ? " ativad" : " desativad") + cfg.artigo + ".", "sucesso");
          carregar();
        }).catch(falhou);
      });

      var editar = botaoIcone(SVG.lapis, "Editar", "hover:bg-primary-soft hover:text-primary-text");
      editar.addEventListener("click", function () { editarNome(li, item); });

      var excluir = botaoIcone(SVG.lixeira, "Excluir", "hover:bg-danger-soft hover:text-danger");
      excluir.addEventListener("click", function () {
        Nexum.confirmar({
          titulo: "Excluir " + cfg.singular + "?",
          mensagem: "“" + item.nome + "” será excluíd" + cfg.artigo + "."
        }).then(function (ok) {
          if (!ok) return;
          enviar(urlDo(cfg.urlExcluir, item.id)).then(function (r) {
            if (!r.ok) { avisar(r.mensagem, r.em_uso ? "info" : "erro"); return; }
            sincronizar(item, true);
            avisar(item.nome + " excluíd" + cfg.artigo + ".", "sucesso");
            carregar();
          }).catch(falhou);
        });
      });

      [nome, uso, chave, editar, excluir].forEach(function (n) { li.appendChild(n); });
      return li;
    }

    function editarNome(li, item) {
      li.innerHTML = "";
      var campo = document.createElement("input");
      campo.type = "text"; campo.maxLength = 60; campo.value = item.nome;
      campo.className = "min-w-0 flex-1 rounded-lg border border-primary bg-surface px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30";
      var salvar = botaoIcone(SVG.check, "Salvar", "text-primary-text hover:bg-primary-soft");
      var cancelar = botaoIcone(SVG.x, "Cancelar", "hover:bg-primary-soft");
      function gravar() {
        enviar(urlDo(cfg.urlSalvar, item.id), { nome: campo.value.trim() }).then(function (r) {
          if (!r.ok) { avisar(r.mensagem, "erro"); campo.focus(); return; }
          sincronizar(r.item);
          avisar("Nome alterado para " + r.item.nome + ".", "sucesso");
          carregar();
        }).catch(falhou);
      }
      salvar.addEventListener("click", gravar);
      cancelar.addEventListener("click", carregar);
      campo.addEventListener("keydown", function (e) {
        if (e.key === "Enter") { e.preventDefault(); gravar(); }
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); carregar(); }
      });
      [campo, salvar, cancelar].forEach(function (n) { li.appendChild(n); });
      campo.focus(); campo.select();
    }

    function cadastrar() {
      var nome = novo.value.trim();
      if (!nome) { avisar("Digite o nome para cadastrar.", "info"); novo.focus(); return; }
      enviar(cfg.urlCriar, { nome: nome, pai: valorPai() }).then(function (r) {
        if (!r.ok) { avisar(r.mensagem, "erro"); novo.focus(); return; }
        sincronizar(r.item);
        escolher(r.item);  // já fica escolhido no cadastro
        avisar(r.item.nome + " cadastrad" + cfg.artigo + " e selecionad" + cfg.artigo + ".", "sucesso");
        novo.value = ""; busca.value = "";
        carregar();
      }).catch(falhou);
    }

    document.querySelectorAll("[data-gerenciar]").forEach(function (botao) {
      botao.addEventListener("click", function () {
        cfg = botao.dataset;
        if (cfg.paiCampo && !valorPai()) {
          Nexum.confirmar({
            tipo: "info", titulo: "Escolha " + (cfg.paiRotulo || "o cadastro principal") + " primeiro",
            mensagem: cfg.titulo + " são cadastrados dentro de " + (cfg.paiRotulo || "outro cadastro") +
                      ". Escolha e clique no + de novo.",
            botao: "Entendi", aviso: ""
          });
          return;
        }
        titulo.textContent = cfg.titulo;
        novo.placeholder = "Nome d" + cfg.artigo + " nov" + cfg.artigo + " " + cfg.singular;
        busca.placeholder = "Pesquisar " + cfg.titulo.toLowerCase();
        busca.value = ""; novo.value = ""; avisar("");
        carregar();
        dialogo.showModal();
        busca.focus();
      });
    });
    busca.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(carregar, 250); });
    adicionar.addEventListener("click", cadastrar);
    novo.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); cadastrar(); } });
  };

  // ---------- Confirmação ("Tem certeza?") — padrão das exclusões do sistema ----------
  //
  // No JavaScript:
  //   Nexum.confirmar({ titulo: "Excluir função?", mensagem: "“Caixa” será excluída." })
  //     .then(function (ok) { if (ok) { ... } });
  // Opções: titulo, mensagem, aviso (2ª linha), botao (texto), tipo ("perigo" | "aviso" | "info").
  //
  // No HTML (sem JavaScript): em <form>, <button> ou <a>
  //   <form data-confirmar="“Caixa” será excluída." data-confirmar-titulo="Excluir função?"> ...
  //   Também: data-confirmar-botao, data-confirmar-tipo, data-confirmar-aviso.
  var ICONES = {
    lixeira: '<svg class="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6M14 11v6"/></svg>',
    alerta: '<svg class="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4M12 17h.01"/></svg>',
    info: '<svg class="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>'
  };
  var TIPOS = {
    perigo: { icone: ICONES.lixeira, cor: "bg-danger-soft text-danger ring-danger-soft/60", botao: "btn-perigo",
              textoBotao: "Excluir", aviso: "Esta ação não pode ser desfeita." },
    aviso:  { icone: ICONES.alerta, cor: "bg-warning/15 text-warning ring-warning/10", botao: "btn-novo",
              textoBotao: "Continuar", aviso: "" },
    info:   { icone: ICONES.info, cor: "bg-primary-soft text-primary-text ring-primary-soft/60", botao: "btn-primario",
              textoBotao: "Confirmar", aviso: "" }
  };
  var janelaConfirmacao = null;

  function criarJanelaConfirmacao() {
    var d = document.createElement("dialog");
    d.id = "confirmacao";
    d.setAttribute("aria-labelledby", "confirmacao-titulo");
    d.setAttribute("aria-describedby", "confirmacao-mensagem");
    d.className = "dialogo-animado m-auto w-[calc(100%-2rem)] max-w-md rounded-2xl border border-line bg-surface p-0 " +
                  "text-ink shadow-2xl backdrop:bg-black/50 backdrop:backdrop-blur-[2px]";
    d.innerHTML =
      '<div class="px-6 pt-7 pb-6 text-center">' +
        '<div data-icone class="mx-auto flex h-14 w-14 items-center justify-center rounded-full ring-8"></div>' +
        '<h2 id="confirmacao-titulo" class="mt-5 text-lg font-semibold"></h2>' +
        '<p id="confirmacao-mensagem" class="mt-2 text-sm text-ink-soft break-words"></p>' +
        '<p data-aviso class="mt-1 text-xs font-medium text-ink-soft/80"></p>' +
      '</div>' +
      '<div class="flex flex-col-reverse gap-2 rounded-b-2xl border-t border-line bg-page/60 px-6 py-4 sm:flex-row">' +
        '<button type="button" data-cancelar class="btn btn-secundario sm:flex-1">Cancelar</button>' +
        '<button type="button" data-ok class="btn sm:flex-1"></button>' +
      '</div>';
    document.body.appendChild(d);
    return d;
  }

  Nexum.confirmar = function (opcoes) {
    opcoes = opcoes || {};
    var d = janelaConfirmacao || (janelaConfirmacao = criarJanelaConfirmacao());
    var tipo = TIPOS[opcoes.tipo] || TIPOS.perigo;
    var icone = d.querySelector("[data-icone]"), ok = d.querySelector("[data-ok]");
    var cancelar = d.querySelector("[data-cancelar]"), aviso = d.querySelector("[data-aviso]");

    icone.className = "mx-auto flex h-14 w-14 items-center justify-center rounded-full ring-8 " + tipo.cor;
    icone.innerHTML = tipo.icone;
    d.querySelector("#confirmacao-titulo").textContent = opcoes.titulo || "Tem certeza?";
    d.querySelector("#confirmacao-mensagem").textContent = opcoes.mensagem || "";
    var textoAviso = opcoes.aviso !== undefined ? opcoes.aviso : tipo.aviso;
    aviso.textContent = textoAviso || "";
    aviso.classList.toggle("hidden", !textoAviso);
    ok.className = "btn sm:flex-1 " + tipo.botao;
    ok.textContent = opcoes.botao || tipo.textoBotao;

    return new Promise(function (resolver) {
      var encerrado = false;
      function encerrar(resposta) {
        if (encerrado) return;
        encerrado = true;
        ok.onclick = cancelar.onclick = d.oncancel = d.onclick = null;
        var reduzir = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        if (reduzir || !d.animate) { d.close(); resolver(resposta); return; }
        var saida = d.animate(
          [{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(6px) scale(0.97)" }],
          { duration: 140, easing: "ease-in" }
        );
        saida.onfinish = function () { d.close(); resolver(resposta); };
      }
      ok.onclick = function () { encerrar(true); };
      cancelar.onclick = function () { encerrar(false); };
      d.oncancel = function (e) { e.preventDefault(); encerrar(false); };          // tecla Esc
      d.onclick = function (e) { if (e.target === d) encerrar(false); };           // clique fora
      d.showModal();
      cancelar.focus();  // o padrão seguro é não excluir
    });
  };

  function opcoesDe(elemento) {
    var ds = elemento.dataset;
    return {
      mensagem: ds.confirmar, titulo: ds.confirmarTitulo, botao: ds.confirmarBotao,
      tipo: ds.confirmarTipo, aviso: ds.confirmarAviso
    };
  }

  // Liga o data-confirmar em todo o sistema (chamado uma vez no base_app.html)
  Nexum.confirmacoes = function () {
    document.addEventListener("submit", function (e) {
      var form = e.target, botao = e.submitter;
      var alvo = botao && botao.dataset.confirmar !== undefined ? botao
               : form.dataset.confirmar !== undefined ? form : null;
      if (!alvo || form._confirmado) return;
      e.preventDefault();
      Nexum.confirmar(opcoesDe(alvo)).then(function (ok) {
        if (!ok) return;
        form._confirmado = true;
        if (botao && form.requestSubmit) form.requestSubmit(botao); else form.submit();
        form._confirmado = false;
      });
    }, true);
    document.addEventListener("click", function (e) {
      var link = e.target.closest && e.target.closest("a[data-confirmar]");
      if (!link) return;
      e.preventDefault();
      Nexum.confirmar(opcoesDe(link)).then(function (ok) { if (ok) window.location.href = link.href; });
    }, true);
  };

  // ---------- Listas suspensas (<details data-dropdown>): fecham ao clicar fora ou com Esc ----------
  Nexum.dropdowns = function () {
    function fecharTodos(exceto) {
      document.querySelectorAll("details[data-dropdown][open]").forEach(function (d) {
        if (d !== exceto) d.open = false;
      });
    }
    document.addEventListener("click", function (e) {
      fecharTodos(e.target.closest && e.target.closest("details[data-dropdown]"));
    });
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      var aberto = document.querySelector("details[data-dropdown][open]");
      if (aberto) { aberto.open = false; aberto.querySelector("summary").focus(); }
    });
  };

  // ---------- Janelas (<dialog>): data-abrir-dialogo="id" e data-fechar-dialogo ----------
  Nexum.dialogos = function () {
    document.querySelectorAll("[data-abrir-dialogo]").forEach(function (botao) {
      botao.addEventListener("click", function () { el(botao.dataset.abrirDialogo).showModal(); });
    });
    document.querySelectorAll("[data-fechar-dialogo]").forEach(function (botao) {
      botao.addEventListener("click", function () { botao.closest("dialog").close(); });
    });
  };

  // ---------- "Excluir selecionados": só libera com algo marcado, mostra quantos e pede confirmação ----------
  // O botão pode ficar fora do <form> (atributo form="..."). Pode ser chamado de novo após o HTMX trocar a tabela.
  Nexum.excluirSelecionados = function () {
    document.querySelectorAll("[data-excluir-selecionados]").forEach(function (botao) {
      var form = botao.form;
      if (!form) return;
      var contagem = botao.querySelector("[data-contagem]");
      function marcados() {
        // form.elements inclui as caixas fora do <form> ligadas por form="..." (ex.: tabela com outros forms por linha)
        return Array.prototype.filter.call(form.elements, function (i) { return i.matches("[data-selecionar]") && i.checked; }).length;
      }
      function atualizar() {
        var total = marcados();
        botao.disabled = total === 0;
        if (contagem) contagem.textContent = total ? " (" + total + ")" : "";
      }
      if (!form._excluirLigado) {
        form._excluirLigado = true;
        document.addEventListener("change", function (e) {
          if (e.target.form === form || e.target.matches("[data-selecionar-todos]")) atualizar();
        });
        form.addEventListener("submit", function (e) {
          if (form._confirmado) return;
          e.preventDefault();
          var total = marcados();
          Nexum.confirmar({
            titulo: botao.dataset.confirmarTitulo || "Excluir selecionados?",
            mensagem: total === 1 ? "1 item selecionado será excluído." : total + " itens selecionados serão excluídos."
          }).then(function (ok) {
            if (!ok) return;
            form._confirmado = true;
            form.submit();
          });
        });
      }
      atualizar();
    });
  };

  // ---------- Campo de senha com botão de olho (data-revelar="id_do_campo") ----------
  Nexum.revelar = function () {
    document.querySelectorAll("[data-revelar]").forEach(function (botao) {
      var campo = el(botao.dataset.revelar);
      botao.addEventListener("click", function () {
        var mostrar = campo.type === "password";
        campo.type = mostrar ? "text" : "password";
        botao.setAttribute("aria-pressed", mostrar ? "true" : "false");
        botao.querySelectorAll("[data-olho]").forEach(function (i) {
          i.classList.toggle("hidden", (i.dataset.olho === "aberto") !== mostrar);
        });
      });
    });
  };

  // ---------- Campos de cadastro sempre atualizados (pílulas) ----------
  // As pílulas (ex.: TAGs) ligadas a um cadastro simples buscam a lista no banco de novo quando a pessoa
  // volta para esta aba do navegador ou chega no campo: o que foi cadastrado em outra aba já aparece.
  // (Os selects viraram busca digitável — Nexum.buscaveis — e consultam o banco a cada busca.)
  Nexum.atualizarOpcoes = function () {
    var campos = [];
    document.querySelectorAll("[data-gerenciar]").forEach(function (b) {
      var alvo = el(b.dataset.alvo);
      if (!alvo || alvo.tagName === "SELECT" || alvo.dataset.atualizando) return;
      alvo.dataset.atualizando = "1";
      campos.push({ alvo: alvo, url: b.dataset.urlLista, ultima: 0 });
    });
    if (!campos.length) return;

    function desenharPilulas(c, itens) {
      var grupo = c.alvo, vazio = grupo.querySelector("[data-vazio]");
      var porId = {};
      itens.forEach(function (i) { porId[String(i.id)] = i; });
      grupo.querySelectorAll("label.pilula").forEach(function (p) {
        var caixa = p.querySelector("input"), item = porId[caixa.value];
        if (item) { p.querySelector("span").textContent = item.nome; }
        if ((!item || !item.ativo) && !caixa.checked) p.remove();  // quem já marcou continua vendo
      });
      itens.forEach(function (i) {
        if (!i.ativo || grupo.querySelector('input[value="' + i.id + '"]')) return;
        var rotulo = document.createElement("label"), caixa = document.createElement("input"), texto = document.createElement("span");
        rotulo.className = "pilula";
        caixa.type = "checkbox"; caixa.name = grupo.dataset.pilulas; caixa.value = String(i.id);
        texto.textContent = i.nome;
        rotulo.appendChild(caixa); rotulo.appendChild(texto);
        grupo.insertBefore(rotulo, vazio);
      });
      if (vazio) vazio.classList.toggle("hidden", !!grupo.querySelector("label.pilula"));
    }

    function atualizar(c, forcar) {
      var agora = Date.now();
      if (!forcar && agora - c.ultima < 3000) return;  // no máximo uma busca a cada 3 s por campo
      c.ultima = agora;
      fetch(c.url).then(function (r) { if (!r.ok) throw r; return r.json(); })
        .then(function (r) { desenharPilulas(c, r.itens); })
        .catch(function () {});  // sem conexão: fica com o que já está na tela
    }

    campos.forEach(function (c) {
      ["pointerenter", "focusin"].forEach(function (ev) { c.alvo.addEventListener(ev, function () { atualizar(c); }); });
    });
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "visible") campos.forEach(function (c) { atualizar(c, true); });
    });
  };

  // ---------- Busca digitável no lugar das listas de cadastro ----------
  // Os selects de cadastro (os que têm o "+" ao lado, ou data-atualizar-url) viram um campo de digitar:
  // a pessoa escreve, o sistema busca no banco e mostra as opções. Sem resultado exato, aparece
  // "Novo: …" com o +, que abre a janela de cadastro já com o nome digitado.
  // O <select> original continua no formulário (escondido) — é ele que vai no POST.
  //   <select data-atualizar-url="/cadastros/grupo/" data-atualizar-todos>  (todos = mostra desativados também)
  var LIMITE_BUSCA = 50;

  Nexum.buscaveis = function () {
    var alvos = [];
    document.querySelectorAll("[data-gerenciar]").forEach(function (b) {
      var s = el(b.dataset.alvo);
      if (s && s.tagName === "SELECT") {
        alvos.push({ select: s, url: b.dataset.urlLista, botao: b, paiCampo: b.dataset.paiCampo, todos: false });
      }
    });
    document.querySelectorAll("select[data-atualizar-url]").forEach(function (s) {
      alvos.push({ select: s, url: s.dataset.atualizarUrl, botao: null, paiCampo: s.dataset.atualizarPai,
                   todos: s.hasAttribute("data-atualizar-todos") });
    });
    alvos.forEach(function (c) { if (!c.select.dataset.buscavel) montarBuscavel(c); });
  };

  function montarBuscavel(c) {
    var select = c.select;
    select.dataset.buscavel = "1";
    var vazia = Array.prototype.find.call(select.options, function (o) { return o.value === ""; });
    var textoVazio = vazia ? vazia.textContent.trim() : "";

    var caixa = document.createElement("div");
    caixa.className = "relative min-w-0 flex-1";
    var campo = document.createElement("input");
    campo.type = "text";
    campo.autocomplete = "off";
    campo.spellcheck = false;
    campo.className = select.className + " pr-9";
    campo.setAttribute("role", "combobox");
    campo.setAttribute("aria-autocomplete", "list");
    campo.setAttribute("aria-expanded", "false");
    if (select.id) {
      // O <label for="id_grupo"> passa a apontar para o campo de digitar
      var rotulo = document.querySelector('label[for="' + select.id + '"]');
      campo.id = select.id + "_busca";
      if (rotulo) rotulo.htmlFor = campo.id;
    }
    if (select.hasAttribute("aria-invalid")) campo.setAttribute("aria-invalid", select.getAttribute("aria-invalid"));
    var lupa = document.createElement("span");
    lupa.className = "pointer-events-none absolute inset-y-0 right-3 flex items-center text-ink-soft";
    lupa.innerHTML = '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>';
    var lista = document.createElement("ul");
    lista.setAttribute("role", "listbox");
    lista.className = "absolute left-0 top-full z-40 mt-1 hidden max-h-72 w-full min-w-64 overflow-auto rounded-xl border border-line " +
                      "bg-surface p-1 text-sm text-ink shadow-xl";
    if (campo.id) { lista.id = campo.id + "_opcoes"; campo.setAttribute("aria-controls", lista.id); }

    select.parentNode.insertBefore(caixa, select);
    caixa.appendChild(select);
    caixa.appendChild(campo);
    caixa.appendChild(lupa);
    caixa.appendChild(lista);
    select.hidden = true;
    select.tabIndex = -1;

    var opcoes = [], ativa = -1, timer = null, pedido = 0;

    function rotuloAtual() {
      var o = select.options[select.selectedIndex];
      return o && o.value !== "" ? o.textContent.trim() : "";
    }
    function mostrarEscolhido() {
      campo.value = rotuloAtual();
      campo.placeholder = textoVazio || "Digite para buscar";
    }
    function fechar() {
      lista.classList.add("hidden");
      campo.setAttribute("aria-expanded", "false");
      ativa = -1;
    }
    function escolher(valor, nome) {
      var o = Array.prototype.find.call(select.options, function (x) { return x.value === String(valor); });
      if (!o && valor !== "") { o = new Option(nome, valor); select.add(o); }
      select.value = String(valor);
      select.dispatchEvent(new Event("change", { bubbles: true }));
      mostrarEscolhido();
      fechar();
    }
    function marcar(i) {
      ativa = i;
      opcoes.forEach(function (o, k) {
        o.li.classList.toggle("bg-primary-soft", k === i);
        o.li.setAttribute("aria-selected", k === i ? "true" : "false");
      });
      if (opcoes[i]) opcoes[i].li.scrollIntoView({ block: "nearest" });
    }
    function linha(texto, classe, acao) {
      var li = document.createElement("li");
      var registro = { li: li, acao: acao };
      li.setAttribute("role", "option");
      li.className = "flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 " + (classe || "");
      li.textContent = texto;
      li.addEventListener("mousedown", function (e) { e.preventDefault(); });  // não tira o foco do campo
      li.addEventListener("click", acao);
      li.addEventListener("mousemove", function () { if (opcoes[ativa] !== registro) marcar(opcoes.indexOf(registro)); });
      opcoes.push(registro);
      lista.appendChild(li);
      return li;
    }
    function aviso(texto) {
      var li = document.createElement("li");
      li.className = "px-3 py-2 text-xs text-ink-soft";
      li.textContent = texto;
      lista.appendChild(li);
    }
    function abrirLista() {
      lista.classList.remove("hidden");
      campo.setAttribute("aria-expanded", "true");
    }
    function abrirCadastro(nome) {
      fechar();
      mostrarEscolhido();
      c.botao.click();  // a mesma janela do "+"
      var novo = el("gerenciador-novo"), dialogo = el("gerenciador");
      if (novo && dialogo && dialogo.open) { novo.value = nome; novo.focus(); }
    }

    function desenhar(itens, mais, termo) {
      lista.innerHTML = "";
      opcoes = [];
      var atual = select.value;
      if (vazia && !termo) linha(textoVazio, "text-ink-soft", function () { escolher("", ""); });
      itens.forEach(function (i) {
        var escolhido = String(i.id) === atual;
        var li = linha(i.nome + (i.ativo ? "" : " (desativado)"), escolhido ? "font-semibold text-primary-text" : "",
                       function () { escolher(i.id, i.nome); });
        if (escolhido) li.insertAdjacentHTML("beforeend", '<span class="ml-auto text-xs">✓</span>');
      });
      if (mais) aviso("Mostrando os " + itens.length + " primeiros. Digite mais para refinar a busca.");
      if (!itens.length) aviso(termo ? "Nada encontrado para “" + termo + "”." : (select.dataset.vazio || "Nenhum cadastro ainda."));
      var exato = itens.some(function (i) { return i.nome.toLowerCase() === termo.toLowerCase(); });
      if (c.botao && termo && !exato) {
        var novo = linha("", "mt-1 border-t border-line font-medium text-primary-text", function () { abrirCadastro(termo); });
        novo.innerHTML = '<span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-primary-soft">+</span>';
        novo.appendChild(document.createTextNode("Novo: “" + termo + "”"));
      }
      abrirLista();
      marcar(termo && opcoes.length ? 0 : -1);  // digitando: Enter já pega a primeira opção
    }

    function buscar() {
      var termo = campo.value.trim();
      if (termo === rotuloAtual()) termo = "";  // abriu sem digitar: mostra tudo
      var pai = "";
      if (c.paiCampo) {
        pai = (el(c.paiCampo) || {}).value || "";
        if (!pai) {
          lista.innerHTML = ""; opcoes = [];
          aviso("Escolha " + ((c.botao && c.botao.dataset.paiRotulo) || select.dataset.atualizarPaiRotulo ||
                              "o cadastro principal") + " primeiro.");
          abrirLista();
          return;
        }
      }
      var meu = ++pedido;
      var url = c.url + (c.url.indexOf("?") >= 0 ? "&" : "?") + "limite=" + LIMITE_BUSCA + "&q=" + encodeURIComponent(termo) + "&pai=" + encodeURIComponent(pai) +
                (c.todos ? "" : "&ativos=1");
      fetch(url).then(function (r) { if (!r.ok) throw r; return r.json(); })
        .then(function (r) { if (meu === pedido && document.activeElement === campo) desenhar(r.itens, r.mais, termo); })
        .catch(function () {
          if (meu !== pedido) return;
          lista.innerHTML = ""; opcoes = [];
          aviso("Não foi possível buscar agora. Tente de novo.");
          abrirLista();
        });
    }

    campo.addEventListener("focus", function () { campo.select(); buscar(); });
    campo.addEventListener("click", function () { if (lista.classList.contains("hidden")) buscar(); });
    campo.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(buscar, 200); });
    campo.addEventListener("keydown", function (e) {
      var aberta = !lista.classList.contains("hidden");
      if (e.key === "ArrowDown") { e.preventDefault(); if (aberta) marcar(Math.min(ativa + 1, opcoes.length - 1)); else buscar(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); marcar(Math.max(ativa - 1, 0)); }
      else if (e.key === "Enter") {
        if (aberta) { e.preventDefault(); if (opcoes[ativa]) opcoes[ativa].acao(); }  // Enter não envia o formulário
      } else if (e.key === "Escape" && aberta) { e.preventDefault(); e.stopPropagation(); mostrarEscolhido(); fechar(); }
    });
    campo.addEventListener("blur", function () {
      setTimeout(function () {
        if (document.activeElement === campo) return;
        // Apagou o texto: fica sem nada escolhido; digitou e não escolheu: volta para o que estava
        if (!campo.value.trim() && select.value !== "" && vazia) escolher("", "");
        else mostrarEscolhido();
        fechar();
      }, 120);
    });
    // O select mudou por fora (ex.: subgrupos recarregados ao trocar o grupo, cadastro feito pelo "+")
    select.addEventListener("change", mostrarEscolhido);
    new MutationObserver(function () { if (document.activeElement !== campo) mostrarEscolhido(); })
      .observe(select, { childList: true });
    mostrarEscolhido();
  }
})();
