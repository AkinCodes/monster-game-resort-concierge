// ============================================================
// Code-Stacking Game Engine
// Teaches code order by having players pick the next correct
// line from shuffled options. Receives GAME_STEPS globally.
// ============================================================

(function () {
  'use strict';

  // ---- State ------------------------------------------------
  const state = {
    currentStep: 0,
    score: 0,
    wrong: 0,
    streak: 0,
    bestStreak: 0,
    startTime: null,
    attemptsPerStep: {},   // stepIndex -> number of wrong attempts
    timerInterval: null,
    audioCtx: null,
    infoPanelTimeout: null,
    isTransitioning: false // guard against double-clicks during animations
  };

  // ---- DOM refs (cached on init) ----------------------------
  let dom = {};

  function cacheDom() {
    dom = {
      progressBar:   document.getElementById('game-progress-bar'),
      progressText:  document.getElementById('game-progress-text'),
      scoreCorrect:  document.getElementById('game-score-correct'),
      scoreWrong:    document.getElementById('game-score-wrong'),
      scoreStreak:   document.getElementById('game-score-streak'),
      scoreAccuracy: document.getElementById('game-score-accuracy'),
      codeStack:     document.getElementById('code-stack'),
      options:       document.getElementById('options-container'),
      infoPanel:     document.getElementById('info-panel'),
      infoCode:      document.getElementById('info-code'),
      infoExplan:    document.getElementById('info-explanation'),
      infoFile:      document.getElementById('info-file'),
      infoCategory:  document.getElementById('info-category'),
      hintPopup:     document.getElementById('hint-popup'),
      completion:    document.getElementById('completion-screen'),
      timer:         document.getElementById('game-timer')
    };
  }

  // ---- Utility helpers --------------------------------------

  /** Fisher-Yates shuffle (returns new array). */
  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  /** Format seconds as mm:ss. */
  function fmtTime(seconds) {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  }

  /** Elapsed seconds since startTime. */
  function elapsed() {
    if (!state.startTime) return 0;
    return (Date.now() - state.startTime) / 1000;
  }

  /** Escape HTML special chars to prevent injection from step data. */
  function esc(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
  }

  // ---- Audio (Web Audio API, graceful fallback) -------------

  function getAudioCtx() {
    if (state.audioCtx) return state.audioCtx;
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) state.audioCtx = new Ctx();
    } catch (_) { /* silent */ }
    return state.audioCtx;
  }

  function playTone(freq, duration, type) {
    const ctx = getAudioCtx();
    if (!ctx) return;
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = type || 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.18, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + duration);
    } catch (_) { /* silent */ }
  }

  function playCorrectSound() {
    playTone(880, 0.15, 'sine');
    setTimeout(function () { playTone(1108, 0.18, 'sine'); }, 80);
  }

  function playWrongSound() {
    playTone(220, 0.25, 'sawtooth');
  }

  // ---- Timer ------------------------------------------------

  function startTimer() {
    state.startTime = Date.now();
    if (state.timerInterval) clearInterval(state.timerInterval);
    state.timerInterval = setInterval(function () {
      if (dom.timer) dom.timer.textContent = fmtTime(elapsed());
    }, 500);
  }

  function stopTimer() {
    if (state.timerInterval) {
      clearInterval(state.timerInterval);
      state.timerInterval = null;
    }
  }

  // ---- Progress & Score UI ----------------------------------

  function updateProgress() {
    const total = GAME_STEPS.length;
    const pct = Math.round((state.currentStep / total) * 100);
    if (dom.progressBar) dom.progressBar.style.width = pct + '%';
    if (dom.progressText) dom.progressText.textContent = state.currentStep + ' / ' + total;
  }

  function updateScore() {
    const total = state.score + state.wrong;
    const accuracy = total === 0 ? 100 : Math.round((state.score / total) * 100);
    if (dom.scoreCorrect)  dom.scoreCorrect.textContent  = state.score;
    if (dom.scoreWrong)    dom.scoreWrong.textContent    = state.wrong;
    if (dom.scoreStreak)   dom.scoreStreak.textContent   = state.streak;
    if (dom.scoreAccuracy) dom.scoreAccuracy.textContent = accuracy + '%';
  }

  // ---- Info Panel -------------------------------------------

  function showInfoPanel(step) {
    if (!dom.infoPanel) return;
    if (dom.infoCode)     dom.infoCode.textContent     = step.codeSnippet || step.correctLine || '';
    if (dom.infoExplan)   dom.infoExplan.innerHTML      = esc(step.explanation || '');
    if (dom.infoFile)     dom.infoFile.textContent       = step.file || '';
    if (dom.infoCategory) dom.infoCategory.textContent   = step.category || '';
    dom.infoPanel.classList.add('visible');
  }

  function hideInfoPanel() {
    if (!dom.infoPanel) return;
    dom.infoPanel.classList.remove('visible');
  }

  // ---- Hint Popup -------------------------------------------

  function showHint(text) {
    if (!dom.hintPopup) return;
    dom.hintPopup.textContent = text;
    dom.hintPopup.classList.add('visible');
    setTimeout(function () {
      dom.hintPopup.classList.remove('visible');
    }, 3000);
  }

  function hideHint() {
    if (dom.hintPopup) dom.hintPopup.classList.remove('visible');
  }

  // ---- Red flash on wrong -----------------------------------

  function flashBackground() {
    document.body.classList.add('wrong-flash');
    setTimeout(function () {
      document.body.classList.remove('wrong-flash');
    }, 400);
  }

  // ---- Code Stack -------------------------------------------

  function addToCodeStack(line, stepIndex) {
    if (!dom.codeStack) return;
    const row = document.createElement('div');
    row.className = 'code-stack-line slide-in';
    row.innerHTML =
      '<span class="code-line-number">' + (stepIndex + 1) + '</span>' +
      '<code>' + esc(line) + '</code>';
    dom.codeStack.appendChild(row);
    // Force reflow so the slide-in animation triggers
    void row.offsetWidth;
    row.classList.add('placed');
    // Auto-scroll to bottom
    dom.codeStack.scrollTop = dom.codeStack.scrollHeight;
  }

  // ---- Render a Step ----------------------------------------

  function renderStep(stepIndex) {
    if (stepIndex >= GAME_STEPS.length) {
      showCompletion();
      return;
    }

    state.isTransitioning = false;
    const step = GAME_STEPS[stepIndex];
    const shuffled = shuffle(step.options);

    if (!dom.options) return;
    dom.options.innerHTML = '';

    shuffled.forEach(function (optionText, i) {
      const card = document.createElement('button');
      card.className = 'option-card';
      card.setAttribute('data-option', optionText);
      card.innerHTML =
        '<span class="option-key">' + (i + 1) + '</span>' +
        '<code>' + esc(optionText) + '</code>' +
        '<span class="option-check">&#10003;</span>';
      card.addEventListener('click', function () {
        handleChoice(optionText, card);
      });
      dom.options.appendChild(card);
    });

    updateProgress();
    hideInfoPanel();
    hideHint();
  }

  // ---- Handle a Choice -------------------------------------

  function handleChoice(chosenOption, cardEl) {
    if (state.isTransitioning) return;

    const stepIndex = state.currentStep;
    const step = GAME_STEPS[stepIndex];

    if (chosenOption === step.correctLine) {
      // --- CORRECT ---
      state.isTransitioning = true;
      playCorrectSound();

      // Green checkmark overlay on the card
      if (cardEl) {
        cardEl.classList.add('correct');
      }

      state.score++;
      state.streak++;
      if (state.streak > state.bestStreak) state.bestStreak = state.streak;
      updateScore();

      // After a beat, add to stack and show info
      setTimeout(function () {
        addToCodeStack(step.correctLine, stepIndex);
        showInfoPanel(step);

        // Disable option cards while info panel is showing
        disableOptions();

        // Auto-advance after 2s, or allow click on Next button inside info panel
        state.infoPanelTimeout = setTimeout(function () {
          advanceStep();
        }, 2000);
      }, 350);

    } else {
      // --- WRONG ---
      playWrongSound();

      state.wrong++;
      state.streak = 0;
      if (!state.attemptsPerStep[stepIndex]) state.attemptsPerStep[stepIndex] = 0;
      state.attemptsPerStep[stepIndex]++;
      updateScore();

      // Shake the wrong card
      if (cardEl) {
        cardEl.classList.add('shake');
        setTimeout(function () {
          cardEl.classList.remove('shake');
        }, 500);
      }

      // Flash background red
      flashBackground();

      // Show hint
      if (step.lineHint) showHint(step.lineHint);
    }
  }

  function disableOptions() {
    if (!dom.options) return;
    var cards = dom.options.querySelectorAll('.option-card');
    cards.forEach(function (c) { c.disabled = true; });
  }

  function advanceStep() {
    if (state.infoPanelTimeout) {
      clearTimeout(state.infoPanelTimeout);
      state.infoPanelTimeout = null;
    }
    hideInfoPanel();
    state.currentStep++;
    if (state.currentStep >= GAME_STEPS.length) {
      showCompletion();
    } else {
      renderStep(state.currentStep);
    }
  }

  // ---- Completion Screen ------------------------------------

  function showCompletion() {
    stopTimer();
    hideInfoPanel();
    if (dom.options) dom.options.innerHTML = '';

    const total = state.score + state.wrong;
    const accuracy = total === 0 ? 100 : Math.round((state.score / total) * 100);
    const time = fmtTime(elapsed());

    // Fill progress to 100%
    if (dom.progressBar) dom.progressBar.style.width = '100%';
    if (dom.progressText) dom.progressText.textContent = GAME_STEPS.length + ' / ' + GAME_STEPS.length;

    if (dom.completion) {
      dom.completion.innerHTML =
        '<div class="completion-content">' +
          '<h2>Build Complete!</h2>' +
          '<div class="completion-stats">' +
            '<div class="stat-item"><span class="stat-value">' + state.score + '/' + GAME_STEPS.length + '</span><span class="stat-label">Correct</span></div>' +
            '<div class="stat-item"><span class="stat-value">' + state.wrong + '</span><span class="stat-label">Mistakes</span></div>' +
            '<div class="stat-item"><span class="stat-value">' + accuracy + '%</span><span class="stat-label">Accuracy</span></div>' +
            '<div class="stat-item"><span class="stat-value">' + time + '</span><span class="stat-label">Time</span></div>' +
            '<div class="stat-item"><span class="stat-value">' + state.bestStreak + '</span><span class="stat-label">Best Streak</span></div>' +
          '</div>' +
          '<div class="completion-grade">' + getGrade(accuracy) + '</div>' +
          '<button class="play-again-btn" onclick="playAgain()">Play Again</button>' +
        '</div>';
      dom.completion.classList.add('visible');
    }
  }

  function getGrade(accuracy) {
    if (accuracy === 100) return '<span class="grade grade-s">S  PERFECT</span>';
    if (accuracy >= 90)   return '<span class="grade grade-a">A  Excellent</span>';
    if (accuracy >= 75)   return '<span class="grade grade-b">B  Great</span>';
    if (accuracy >= 60)   return '<span class="grade grade-c">C  Good</span>';
    return '<span class="grade grade-d">D  Keep Practicing</span>';
  }

  // ---- Play Again -------------------------------------------

  function playAgain() {
    state.currentStep = 0;
    state.score = 0;
    state.wrong = 0;
    state.streak = 0;
    state.bestStreak = 0;
    state.startTime = null;
    state.attemptsPerStep = {};
    state.isTransitioning = false;

    if (state.infoPanelTimeout) {
      clearTimeout(state.infoPanelTimeout);
      state.infoPanelTimeout = null;
    }

    if (dom.codeStack)   dom.codeStack.innerHTML = '';
    if (dom.completion)  {
      dom.completion.classList.remove('visible');
      dom.completion.innerHTML = '';
    }
    hideInfoPanel();
    hideHint();
    updateScore();

    startTimer();
    renderStep(0);
  }

  // ---- Init -------------------------------------------------

  function initGame() {
    cacheDom();

    // Reset state
    state.currentStep = 0;
    state.score = 0;
    state.wrong = 0;
    state.streak = 0;
    state.bestStreak = 0;
    state.attemptsPerStep = {};
    state.isTransitioning = false;

    if (dom.codeStack)  dom.codeStack.innerHTML = '';
    if (dom.completion) {
      dom.completion.classList.remove('visible');
      dom.completion.innerHTML = '';
    }

    updateScore();
    startTimer();
    renderStep(0);
  }

  // ---- Keyboard support -------------------------------------

  document.addEventListener('keydown', function (e) {
    // 1-5 keys to pick options
    var key = parseInt(e.key, 10);
    if (key >= 1 && key <= 9 && dom.options) {
      var cards = dom.options.querySelectorAll('.option-card');
      if (key <= cards.length && !cards[key - 1].disabled) {
        cards[key - 1].click();
      }
      return;
    }

    // Enter or Space to advance when info panel is open
    if ((e.key === 'Enter' || e.key === ' ') && dom.infoPanel && dom.infoPanel.classList.contains('visible')) {
      e.preventDefault();
      advanceStep();
      return;
    }
  });

  // ---- Click handler for info panel "Next" ------------------
  // If the info panel itself is clicked, advance
  document.addEventListener('click', function (e) {
    if (dom.infoPanel && dom.infoPanel.classList.contains('visible')) {
      // Check if click was on / inside the info panel
      if (dom.infoPanel.contains(e.target)) {
        advanceStep();
      }
    }
  });

  // ---- Expose public API ------------------------------------
  window.initGame   = initGame;
  window.playAgain  = playAgain;

  // Auto-init when DOM is ready, if GAME_STEPS exists
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      if (typeof GAME_STEPS !== 'undefined' && GAME_STEPS.length) initGame();
    });
  } else {
    if (typeof GAME_STEPS !== 'undefined' && GAME_STEPS.length) initGame();
  }

})();
