(function () {
  const STORAGE_ACCENT = "typeng_pronunciation_accent";
  const STORAGE_AUTOPLAY = "typeng_pronunciation_autoplay";
  const AUDIO_START_TIMEOUT_MS = 550;
  const audioCache = new Map();
  let activeAudio = null;

  function getAccent() {
    return localStorage.getItem(STORAGE_ACCENT) || "us";
  }

  function setAccent(value) {
    localStorage.setItem(STORAGE_ACCENT, value === "uk" ? "uk" : "us");
  }

  function isAutoplayEnabled() {
    return localStorage.getItem(STORAGE_AUTOPLAY) !== "off";
  }

  function setAutoplay(value) {
    localStorage.setItem(STORAGE_AUTOPLAY, value ? "on" : "off");
  }

  function youdaoUrl(word, accent) {
    const type = accent === "uk" ? "1" : "2";
    return `https://dict.youdao.com/dictvoice?type=${type}&audio=${encodeURIComponent(word)}`;
  }

  function audioCacheKey(word, accent) {
    return `${accent}:${word.toLowerCase()}`;
  }

  function audioForWord(word, accent) {
    const key = audioCacheKey(word, accent);
    if (!audioCache.has(key)) {
      const audio = new Audio(youdaoUrl(word, accent));
      audio.preload = "auto";
      audioCache.set(key, audio);
    }
    return audioCache.get(key);
  }

  function preloadWord(word, accent) {
    const audio = audioForWord(word, accent);
    try {
      audio.load();
    } catch (_) {
      // Some browsers defer media loading until a user gesture. Playback will
      // still retry the same element when the learner asks for it.
    }
  }

  function speakWithBrowser(word, accent) {
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
      return false;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(word);
    utterance.lang = accent === "uk" ? "en-GB" : "en-US";
    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find((voice) => voice.lang === utterance.lang)
      || voices.find((voice) => voice.lang && voice.lang.toLowerCase().startsWith(utterance.lang.toLowerCase()));
    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }
    utterance.rate = 0.9;
    window.speechSynthesis.speak(utterance);
    return true;
  }

  function playRecordedAudio(word, accent, timeoutMs) {
    return new Promise((resolve, reject) => {
      const audio = audioForWord(word, accent);
      let settled = false;
      if (activeAudio && activeAudio !== audio) {
        activeAudio.pause();
      }
      activeAudio = audio;
      audio.currentTime = 0;
      const timeout = window.setTimeout(() => {
        if (!settled) {
          settled = true;
          audio.pause();
          reject(new Error("audio-timeout"));
        }
      }, timeoutMs);

      audio.addEventListener("playing", () => {
        if (!settled) {
          settled = true;
          window.clearTimeout(timeout);
          resolve();
        }
      }, { once: true });
      audio.addEventListener("error", () => {
        if (!settled) {
          settled = true;
          window.clearTimeout(timeout);
          reject(new Error("audio-error"));
        }
      }, { once: true });

      audio.play().catch((error) => {
        if (!settled) {
          settled = true;
          window.clearTimeout(timeout);
          reject(error);
        }
      });
    });
  }

  async function playWord(word, options) {
    const accent = options && options.accent ? options.accent : getAccent();
    const button = options && options.button ? options.button : null;
    const originalText = button ? button.textContent : "";
    if (button) {
      button.setAttribute("aria-busy", "true");
    }

    try {
      await playRecordedAudio(word, accent, AUDIO_START_TIMEOUT_MS);
    } catch (_) {
      if (button) {
        button.textContent = "浏览器语音";
        window.setTimeout(() => {
          button.textContent = originalText;
        }, 900);
      }
      speakWithBrowser(word, accent);
    } finally {
      if (button) {
        button.removeAttribute("aria-busy");
      }
    }
  }

  function bindPronunciationSettings() {
    document.querySelectorAll("[data-pronunciation-accent]").forEach((select) => {
      select.value = getAccent();
      select.addEventListener("change", () => setAccent(select.value));
    });

    document.querySelectorAll("[data-pronunciation-autoplay]").forEach((checkbox) => {
      checkbox.checked = isAutoplayEnabled();
      checkbox.addEventListener("change", () => setAutoplay(checkbox.checked));
    });
  }

  function bindPlayButtons() {
    document.querySelectorAll("[data-play-word]").forEach((button) => {
      button.addEventListener("click", () => {
        const word = button.getAttribute("data-play-word");
        if (word) {
          playWord(word, { button });
        }
      });
    });
  }

  function bindAutoPlay() {
    const target = document.querySelector("[data-auto-play-word]");
    if (!target || !isAutoplayEnabled()) {
      return;
    }

    const word = target.getAttribute("data-auto-play-word");
    if (!word) {
      return;
    }

    let didPlay = false;
    const tryPlay = () => {
      if (didPlay) {
        return;
      }
      didPlay = true;
      window.removeEventListener("click", tryPlay);
      window.removeEventListener("keydown", tryPlay);
      playWord(word);
    };

    // Browsers block audio autoplay until the page has had a user gesture.
    // If activation already exists (e.g. mid-session navigation), play now;
    // otherwise wait for the first click/keypress instead of firing an eager
    // timer that would silently fail and consume the one recovery attempt.
    const activation = window.navigator && window.navigator.userActivation;
    if (activation && activation.hasBeenActive) {
      tryPlay();
    } else {
      window.addEventListener("click", tryPlay, { once: true });
      window.addEventListener("keydown", tryPlay, { once: true });
    }
  }

  function preloadUpcomingWord() {
    const target = document.querySelector("[data-preload-word]");
    if (!target || !isAutoplayEnabled()) {
      return;
    }
    const word = target.getAttribute("data-preload-word");
    if (word) {
      preloadWord(word, getAccent());
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindPronunciationSettings();
    bindPlayButtons();
    preloadUpcomingWord();
    bindAutoPlay();
  });
})();
