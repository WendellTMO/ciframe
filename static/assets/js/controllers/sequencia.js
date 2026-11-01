angular.module('deciframeApp').controller('SequenciaController', function($http, $window, ngProgressFactory, $anchorScroll, $location, GENEROS, ACORDES) {
  var COR = '#2E1C74';
  var vm = this;
  vm.sequenciasFamosas = [];
  vm.minhaSequencia = {};
  vm.acordes = ACORDES;
  vm.modalAberta = false;
  vm.novaSequencia = [];
  vm.cadastrando = false;
  vm.erroCadastro = "";
  vm.avisoCadastro = "";
  vm.isSearching = false;
  vm.showSearchResultsCount = false;
  vm.esfigeSpeech =  "";
  vm.musics = [];
  vm.generos = GENEROS;
  vm.meuGenero = "";
  vm.progressbar = ngProgressFactory.createInstance();

  var converteSequencia = function(sequencia) {
    var acordes = [];
    for (var i = 0; i < sequencia.acordes.length; i++) {
      acordes.push({ 'acorde': sequencia.acordes[i], 'cor': COR });
    }
    return { 'id': sequencia.id, 'acordes': acordes };
  }

  var buscaSequenciaPorId = function(id) {
    for (var i = 0; i < vm.sequenciasFamosas.length; i++) {
      if (vm.sequenciasFamosas[i].id === id) {
        return vm.sequenciasFamosas[i];
      }
    }
    return null;
  }

  $http.get('sequencias')
    .success(function(data) {
      vm.sequenciasFamosas = data.map(converteSequencia);
    })
    .error(function() {
      vm.erroCadastro = "Não foi possível carregar as sequências.";
    });

  vm.temAcorde = function(acorde) {
    if (vm.minhaSequencia.acordes) {
      return (vm.minhaSequencia.acordes.indexOf(acorde) > -1);
    } else {
      return false;
    }
  }

  var createChordsString = function(chords) {
    var str = "";
    for (var i = 0; i < chords.length; i++) {
      str = str.concat(chords[i].acorde, ',');
    }
    return str.substring(0, str.length-1);
  }

  vm.abrirModal = function() {
    vm.novaSequencia = [];
    vm.erroCadastro = "";
    vm.avisoCadastro = "";
    vm.modalAberta = true;
  }

  vm.fecharModal = function() {
    vm.modalAberta = false;
    vm.novaSequencia = [];
    vm.erroCadastro = "";
  }

  vm.adicionarAcorde = function(acorde) {
    vm.novaSequencia.push({ 'acorde': acorde.acorde, 'cor': acorde.cor });
    vm.erroCadastro = "";
  }

  vm.removerAcorde = function(index) {
    vm.novaSequencia.splice(index, 1);
    vm.erroCadastro = "";
  }

  vm.salvarSequencia = function() {
    var acordes = [];
    for (var i = 0; i < vm.novaSequencia.length; i++) {
      acordes.push(vm.novaSequencia[i].acorde);
    }

    vm.cadastrando = true;
    vm.erroCadastro = "";

    $http.post('sequencias', { 'acordes': acordes })
      .success(function(data) {
        vm.cadastrando = false;
        vm.sequenciasFamosas.push(converteSequencia(data));
        vm.fecharModal();
      })
      .error(function(data, status) {
        vm.cadastrando = false;
        if (status === 409) {
          var existente = buscaSequenciaPorId(data.id);
          if (existente) {
            vm.pesquisarPorSequencia(existente);
          }
          vm.avisoCadastro = "Essa sequência já existe. Selecionei ela para você.";
          vm.fecharModal();
        } else {
          vm.erroCadastro = (data && data.erro) || "Ops! Algo errado.";
        }
      });
  }

  vm.pesquisarPorSequencia = function(sequencia) {
    if (sequencia) {
      vm.minhaSequencia = sequencia;
    }
    vm.progressbar.start();
    vm.esfigeSpeech = "Procurando músicas com base na sequencia...";
    vm.isSearching = true;
    vm.musics = [];

    var params = { 'sequencia': createChordsString(vm.minhaSequencia.acordes) };
    if (vm.meuGenero !== "" && vm.meuGenero !== null) {
      params.generos = vm.meuGenero;
    }
    $http.get('similares', { 'params': params })
      .success(function(data) {
        vm.progressbar.complete();
        vm.esfigeSpeech = "Encontrei essas músicas";
        vm.isSearching = false;
        vm.showSearchResultsCount = true;
        vm.musics = data;
      })
      .error(function(data) {
        vm.esfigeSpeech = "Ops! Algo errado.";
        vm.isSearching = false;
        vm.showSearchResultsCount = false;
      });
  }

  vm.limparPesquisa = function() {
    vm.minhaSequencia = {};
    vm.musics = [];
  }

  vm.goToLirics = function(music) {
    $window.open(music.url);
  };

  vm.goToResults = function() {
    vm.showSearchResultsCount = false;
    $("body").animate({scrollTop: $("#results").offset().top}, "slow");
  };
});
