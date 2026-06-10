(function () {
    'use strict';

    var QUALITY_ORDER = ['480', '720', '1080', '4k'];
    var QUALITY_LABELS = { '480': '480p', '720': '720p', '1080': '1080p', '4k': '4K' };

    function isHls(url) {
        return /\.m3u8(\?|$)/i.test(url);
    }

    function getAvailableQualities(streams) {
        return QUALITY_ORDER.filter(function (q) { return streams[q]; });
    }

    function detectQualityByConnection() {
        var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
        if (conn) {
            var downlink = conn.downlink || 0;
            var type = conn.effectiveType || '';
            if (downlink >= 20 || type === '4g' && downlink >= 15) return '4k';
            if (downlink >= 8 || type === '4g') return '1080';
            if (downlink >= 3 || type === '3g') return '720';
            return '480';
        }
        return '720';
    }

    function pickBestQuality(streams, target) {
        var available = getAvailableQualities(streams);
        if (!available.length) return null;
        var targetIdx = QUALITY_ORDER.indexOf(target);
        if (targetIdx === -1) return available[0];
        for (var i = targetIdx; i >= 0; i--) {
            if (streams[QUALITY_ORDER[i]]) return QUALITY_ORDER[i];
        }
        return available[0];
    }

    function estimateByProbe(streams, callback) {
        var testUrl = streams['720'] || streams['480'] || streams['1080'] || streams['4k'];
        if (!testUrl || isHls(testUrl)) {
            callback(detectQualityByConnection());
            return;
        }
        var start = performance.now();
        var xhr = new XMLHttpRequest();
        xhr.open('HEAD', testUrl, true);
        xhr.onload = function () {
            var elapsed = (performance.now() - start) / 1000;
            var size = parseInt(xhr.getResponseHeader('Content-Length') || '0', 10);
            if (size > 0 && elapsed > 0) {
                var mbps = (size * 8) / (elapsed * 1000000);
                if (mbps >= 20) callback('4k');
                else if (mbps >= 8) callback('1080');
                else if (mbps >= 3) callback('720');
                else callback('480');
            } else {
                callback(detectQualityByConnection());
            }
        };
        xhr.onerror = function () { callback(detectQualityByConnection()); };
        xhr.send();
    }

    function injectProtectionStyles() {
        if (document.getElementById('kino-player-protection-css')) return;
        var style = document.createElement('style');
        style.id = 'kino-player-protection-css';
        style.textContent = [
            '.player-video-wrap{position:relative;background:#000;overflow:hidden}',
            '.player-capture-shield{display:none;position:absolute;inset:0;z-index:30;background:#000}',
            '.player-video-wrap.is-protected .player-capture-shield{display:block}',
            '.player-video-wrap.is-protected video{visibility:hidden!important;opacity:0!important;filter:brightness(0)!important}',
            '.player-capture-shield-global{display:none;position:fixed;inset:0;z-index:2147483646;background:#000}',
            '.player-capture-shield-global.is-active{display:block}',
            '.player-video-wrap video{-webkit-user-select:none;user-select:none;-webkit-touch-callout:none}'
        ].join('');
        document.head.appendChild(style);
    }

    function setupCaptureProtection(wrap, video, onSuspend, onResume) {
        var shield = document.createElement('div');
        shield.className = 'player-capture-shield';
        shield.setAttribute('aria-hidden', 'true');
        wrap.appendChild(shield);

        var globalShield = document.querySelector('.player-capture-shield-global');
        if (!globalShield) {
            globalShield = document.createElement('div');
            globalShield.className = 'player-capture-shield-global';
            document.body.appendChild(globalShield);
        }

        var active = false;
        var wasPlaying = false;
        var suspendTimer = null;

        function activate(reason) {
            if (active) return;
            active = true;
            wasPlaying = !video.paused && !video.ended;
            wrap.classList.add('is-protected');
            if (reason === 'display-capture' || reason === 'printscreen') {
                globalShield.classList.add('is-active');
            }
            video.pause();
            if (document.fullscreenElement) {
                globalShield.classList.add('is-active');
                document.exitFullscreen().catch(function () {});
            }
            if (onSuspend) onSuspend();
        }

        function deactivate() {
            if (!active) return;
            if (!document.hasFocus() || document.hidden) return;
            active = false;
            wrap.classList.remove('is-protected');
            globalShield.classList.remove('is-active');
            if (onResume) onResume();
            if (wasPlaying) {
                video.play().catch(function () {});
            }
        }

        function scheduleActivate() {
            clearTimeout(suspendTimer);
            suspendTimer = setTimeout(activate, 80);
        }

        function scheduleDeactivate() {
            clearTimeout(suspendTimer);
            suspendTimer = setTimeout(deactivate, 120);
        }

        document.addEventListener('visibilitychange', function () {
            if (document.hidden) activate('hidden');
            else scheduleDeactivate();
        });

        window.addEventListener('blur', scheduleActivate);
        window.addEventListener('focus', scheduleDeactivate);

        document.addEventListener('freeze', activate);
        document.addEventListener('resume', scheduleDeactivate);

        document.addEventListener('keyup', function (e) {
            if (e.key === 'PrintScreen') {
                activate('printscreen');
                setTimeout(function () {
                    if (!document.hidden && document.hasFocus()) deactivate();
                }, 2500);
            }
        });

        if (navigator.permissions && navigator.permissions.query) {
            try {
                navigator.permissions.query({ name: 'display-capture' }).then(function (result) {
                    function syncCapturePermission() {
                        if (result.state === 'granted') activate('display-capture');
                        else if (!document.hidden && document.hasFocus()) deactivate();
                    }
                    result.addEventListener('change', syncCapturePermission);
                    syncCapturePermission();
                }).catch(function () {});
            } catch (e) { /* not supported */ }
        }

        setInterval(function () {
            if (document.hidden || !document.hasFocus()) return;
            if (!navigator.permissions || !navigator.permissions.query) return;
            try {
                navigator.permissions.query({ name: 'display-capture' }).then(function (result) {
                    if (result.state === 'granted') activate('display-capture');
                }).catch(function () {});
            } catch (e) { /* ignore */ }
        }, 2000);

        video.addEventListener('contextmenu', function (e) { e.preventDefault(); });
        video.setAttribute('controlsList', 'nodownload noremoteplayback');
        video.setAttribute('disablePictureInPicture', '');
        video.setAttribute('draggable', 'false');
        video.disablePictureInPicture = true;

        return {
            activate: activate,
            deactivate: deactivate
        };
    }

    window.KinoPlayer = {
        init: function (containerId, streams) {
            var container = document.getElementById(containerId);
            if (!container) return;

            injectProtectionStyles();

            var available = getAvailableQualities(streams);
            if (!available.length) {
                container.innerHTML = '<div class="player-empty">Видео пока не добавлено</div>';
                return;
            }

            var currentMode = localStorage.getItem('kino_quality_mode') || 'auto';
            var currentQuality = null;
            var hlsInstance = null;
            var video = document.createElement('video');
            video.controls = true;
            video.playsInline = true;
            video.preload = 'metadata';
            video.style.width = '100%';
            video.style.background = '#000';

            var wrap = document.createElement('div');
            wrap.className = 'player-video-wrap';
            wrap.appendChild(video);

            var controls = document.createElement('div');
            controls.className = 'player-quality-bar';

            var label = document.createElement('span');
            label.className = 'player-quality-label';
            label.textContent = 'Качество:';

            var select = document.createElement('select');
            select.className = 'player-quality-select';

            var autoOpt = document.createElement('option');
            autoOpt.value = 'auto';
            autoOpt.textContent = 'Авто';
            select.appendChild(autoOpt);

            available.forEach(function (q) {
                var opt = document.createElement('option');
                opt.value = q;
                opt.textContent = QUALITY_LABELS[q];
                select.appendChild(opt);
            });

            var statusEl = document.createElement('span');
            statusEl.className = 'player-quality-status';

            controls.appendChild(label);
            controls.appendChild(select);
            controls.appendChild(statusEl);

            container.innerHTML = '';
            container.appendChild(wrap);
            container.appendChild(controls);

            function updateStatus(q, isAuto) {
                statusEl.textContent = isAuto
                    ? 'Авто → ' + QUALITY_LABELS[q]
                    : QUALITY_LABELS[q];
            }

            function destroyHls() {
                if (hlsInstance) {
                    hlsInstance.destroy();
                    hlsInstance = null;
                }
            }

            function clearVideoSource() {
                destroyHls();
                video.pause();
                video.removeAttribute('src');
                video.load();
            }

            function loadQuality(quality, isAuto) {
                var url = streams[quality];
                if (!url) return;
                currentQuality = quality;
                destroyHls();
                video.pause();

                if (isHls(url) && window.Hls && Hls.isSupported()) {
                    hlsInstance = new Hls({
                        startLevel: -1,
                        capLevelToPlayerSize: true,
                    });
                    hlsInstance.loadSource(url);
                    hlsInstance.attachMedia(video);
                    hlsInstance.on(Hls.Events.MANIFEST_PARSED, function () {
                        if (!wrap.classList.contains('is-protected')) {
                            video.play().catch(function () {});
                        }
                    });
                } else if (video.canPlayType('application/vnd.apple.mpegurl') && isHls(url)) {
                    video.src = url;
                    if (!wrap.classList.contains('is-protected')) {
                        video.play().catch(function () {});
                    }
                } else {
                    video.src = url;
                    if (!wrap.classList.contains('is-protected')) {
                        video.play().catch(function () {});
                    }
                }
                updateStatus(quality, isAuto);
            }

            function reloadCurrent() {
                if (!currentQuality) return;
                loadQuality(currentQuality, currentMode === 'auto');
            }

            setupCaptureProtection(wrap, video, clearVideoSource, reloadCurrent);

            function applyMode(mode) {
                currentMode = mode;
                localStorage.setItem('kino_quality_mode', mode);
                if (mode === 'auto') {
                    select.value = 'auto';
                    estimateByProbe(streams, function (detected) {
                        var best = pickBestQuality(streams, detected);
                        loadQuality(best, true);
                    });
                } else {
                    select.value = mode;
                    loadQuality(mode, false);
                }
            }

            select.addEventListener('change', function () {
                applyMode(select.value);
            });

            if (currentMode !== 'auto' && streams[currentMode]) {
                select.value = currentMode;
                loadQuality(currentMode, false);
            } else {
                applyMode('auto');
            }

            var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
            if (conn && conn.addEventListener) {
                conn.addEventListener('change', function () {
                    if (currentMode === 'auto') applyMode('auto');
                });
            }
        }
    };
})();
