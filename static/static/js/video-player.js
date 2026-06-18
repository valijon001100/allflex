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
            '.player-video-wrap video{-webkit-user-select:none;user-select:none;-webkit-touch-callout:none;-webkit-user-drag:none;user-drag:none}',
            '.player-video-wrap--burn video{position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;overflow:hidden;clip:rect(0,0,0,0)}',
            '.player-video-canvas{display:block;width:100%;background:#000;cursor:pointer}',
            '.player-video-wrap.is-protected .player-video-canvas{visibility:hidden!important;opacity:0!important}',
            '.movie-viewer-watermark{position:absolute;left:12px;top:12px;z-index:35;font-size:10px;font-weight:600;letter-spacing:.5px;color:rgba(255,255,255,.92);text-shadow:0 1px 3px rgba(0,0,0,.9),0 0 6px rgba(0,0,0,.6);pointer-events:none;user-select:none;font-family:Arial,Helvetica,sans-serif;white-space:nowrap;transition:left 3.5s ease-in-out,top 3.5s ease-in-out}',
            '.player-seek-bar{display:flex;align-items:center;gap:8px;padding:8px 14px;background:#1a1d27;color:#fff}',
            '.player-seek-btn{background:#2a2d3a;border:1px solid #4067b7;color:#fff;border-radius:4px;padding:4px 10px;font-size:12px;cursor:pointer;white-space:nowrap;line-height:1.2}',
            '.player-seek-btn:hover{background:#4067b7}',
            '.player-seek-range{flex:1;min-width:0;height:6px;cursor:pointer;accent-color:#e50914}',
            '.player-seek-time{font-size:12px;color:#9ca3af;white-space:nowrap;min-width:96px;text-align:right}',
            '.player-fs-btn{min-width:36px;padding:4px 8px}',
            '.player-video-wrap:fullscreen,.player-video-wrap:-webkit-full-screen{width:100%;height:100%;background:#000;display:flex;align-items:center;justify-content:center}',
            '.player-video-wrap:fullscreen video,.player-video-wrap:-webkit-full-screen video{width:100%;height:100%;max-height:100%;object-fit:contain}',
            '.player-video-wrap:fullscreen .movie-viewer-watermark,.player-video-wrap:-webkit-full-screen .movie-viewer-watermark{font-size:12px;z-index:2147483647}'
        ].join('');
        document.head.appendChild(style);
    }

    function startCanvasBurn(wrap, video, canvas, watermarkText, options) {
        options = options || {};
        var ctx = canvas.getContext('2d');
        var rafId = null;
        var motionTimer = null;
        var wmX = 12;
        var wmY = 12;
        var wmTargetX = 12;
        var wmTargetY = 12;
        var fontSize = 10;

        function getBottomPad() {
            if (typeof options.getBottomPad === 'function') {
                return options.getBottomPad();
            }
            return 12;
        }

        function measureText() {
            ctx.font = '600 ' + fontSize + 'px Arial, Helvetica, sans-serif';
            return ctx.measureText(watermarkText);
        }

        function getBounds() {
            var margin = 12;
            var pad = getBottomPad();
            var metrics = measureText();
            var textW = metrics.width || 90;
            var textH = fontSize + 4;
            var maxX = Math.max(margin, canvas.width - textW - margin);
            var maxY = Math.max(margin, canvas.height - textH - pad);
            return { margin: margin, maxX: maxX, maxY: maxY, textH: textH };
        }

        function pickTarget() {
            var b = getBounds();
            wmTargetX = b.margin + Math.random() * Math.max(0, b.maxX - b.margin);
            wmTargetY = b.margin + Math.random() * Math.max(0, b.maxY - b.margin);
        }

        function syncSize() {
            var vw = video.videoWidth;
            var vh = video.videoHeight;
            var wrapW = wrap.clientWidth || video.clientWidth;
            if (!wrapW) return;
            var displayH;
            if (vw && vh) {
                displayH = Math.round(wrapW * vh / vw);
            } else {
                displayH = Math.round(wrapW * 9 / 16);
            }
            canvas.style.width = wrapW + 'px';
            canvas.style.height = displayH + 'px';
            if (canvas.width !== wrapW || canvas.height !== displayH) {
                canvas.width = wrapW;
                canvas.height = displayH;
                pickTarget();
                wmX = wmTargetX;
                wmY = wmTargetY;
            }
        }

        function drawWatermark() {
            if (!watermarkText) return;
            var metrics = measureText();
            ctx.font = '600 ' + fontSize + 'px Arial, Helvetica, sans-serif';
            ctx.fillStyle = 'rgba(255,255,255,0.92)';
            ctx.shadowColor = 'rgba(0,0,0,0.9)';
            ctx.shadowOffsetX = 0;
            ctx.shadowOffsetY = 1;
            ctx.shadowBlur = 3;
            ctx.fillText(watermarkText, wmX, wmY + fontSize);
            ctx.shadowBlur = 0;
            ctx.fillStyle = 'rgba(255,255,255,0.18)';
            ctx.font = '600 8px Arial, Helvetica, sans-serif';
            ctx.fillText(watermarkText, 8, canvas.height - 10);
        }

        function renderFrame() {
            if (!wrap.isConnected) return;
            wmX += (wmTargetX - wmX) * 0.035;
            wmY += (wmTargetY - wmY) * 0.035;
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            if (video.readyState >= 2 && video.videoWidth) {
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            } else {
                ctx.fillStyle = '#000';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
            }
            drawWatermark();
            rafId = requestAnimationFrame(renderFrame);
        }

        function scheduleMotion() {
            clearTimeout(motionTimer);
            motionTimer = setTimeout(function () {
                pickTarget();
                scheduleMotion();
            }, 3500 + Math.random() * 2500);
        }

        function onResize() {
            syncSize();
        }

        canvas.addEventListener('click', function () {
            if (video.paused) {
                video.play().catch(function () {});
            } else {
                video.pause();
            }
        });

        video.addEventListener('loadedmetadata', syncSize);
        video.addEventListener('loadeddata', syncSize);
        window.addEventListener('resize', onResize);
        syncSize();
        pickTarget();
        wmX = wmTargetX;
        wmY = wmTargetY;
        scheduleMotion();
        renderFrame();

        return {
            syncSize: syncSize,
            setFontSize: function (size) {
                fontSize = size;
                pickTarget();
            },
            destroy: function () {
                cancelAnimationFrame(rafId);
                clearTimeout(motionTimer);
                window.removeEventListener('resize', onResize);
            },
        };
    }

    function startWatermarkMotion(wrap, watermark, options) {
        options = options || {};
        var motionTimer = null;

        function getBottomPad() {
            if (typeof options.getBottomPad === 'function') {
                return options.getBottomPad();
            }
            return 52;
        }

        function moveWatermark() {
            var w = wrap.clientWidth;
            var h = wrap.clientHeight;
            if (!w || !h) return;
            var wmW = watermark.offsetWidth || 90;
            var wmH = watermark.offsetHeight || 14;
            var margin = 12;
            var pad = getBottomPad();
            var maxX = Math.max(margin, w - wmW - margin);
            var maxY = Math.max(margin, h - wmH - pad);
            var x = margin + Math.random() * Math.max(0, maxX - margin);
            var y = margin + Math.random() * Math.max(0, maxY - margin);
            watermark.style.left = Math.round(x) + 'px';
            watermark.style.top = Math.round(y) + 'px';
            watermark.style.bottom = 'auto';
            watermark.style.right = 'auto';
            watermark.style.transform = 'none';
        }

        function scheduleNext(delay) {
            clearTimeout(motionTimer);
            motionTimer = setTimeout(function () {
                moveWatermark();
                scheduleNext(3500 + Math.random() * 2500);
            }, delay);
        }

        function onResize() {
            moveWatermark();
        }

        requestAnimationFrame(function () {
            moveWatermark();
            scheduleNext(4000);
        });
        window.addEventListener('resize', onResize);

        return {
            reposition: moveWatermark,
            destroy: function () {
                clearTimeout(motionTimer);
                window.removeEventListener('resize', onResize);
            },
        };
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

        wrap.addEventListener('contextmenu', function (e) { e.preventDefault(); });
        wrap.addEventListener('dragstart', function (e) { e.preventDefault(); });
        wrap.addEventListener('drop', function (e) { e.preventDefault(); });
        wrap.addEventListener('selectstart', function (e) { e.preventDefault(); });
        video.addEventListener('contextmenu', function (e) { e.preventDefault(); });
        video.setAttribute('controlsList', 'nodownload noremoteplayback');
        video.setAttribute('disablePictureInPicture', '');
        video.setAttribute('draggable', 'false');
        video.disablePictureInPicture = true;

        document.addEventListener('keydown', function (e) {
            if (!wrap.isConnected) return;
            var key = (e.key || '').toLowerCase();
            if (e.ctrlKey && (key === 's' || key === 'u' || key === 'p')) {
                e.preventDefault();
            }
            if (e.ctrlKey && e.shiftKey && (key === 's' || key === 'i' || key === 'j' || key === 'c')) {
                e.preventDefault();
            }
        });

        return {
            activate: activate,
            deactivate: deactivate
        };
    }

    window.KinoPlayer = {
        startWatermarkMotion: startWatermarkMotion,
        startCanvasBurn: startCanvasBurn,
        init: function (containerId, streams, options) {
            options = options || {};
            var container = document.getElementById(containerId);
            if (!container) return;

            injectProtectionStyles();

            var available = getAvailableQualities(streams);
            if (!available.length) {
                container.innerHTML = '<div class="player-empty">Видео пока не добавлено</div>';
                return;
            }

            var currentMode = options.iptv ? '720' : (localStorage.getItem('kino_quality_mode') || 'auto');
            var currentQuality = null;
            var hlsInstance = null;
            var useCanvasBurn = !options.serverBurn && !options.iptv;
            var video = document.createElement('video');
            video.controls = !useCanvasBurn;
            video.playsInline = true;
            video.preload = 'metadata';
            video.style.width = '100%';
            video.style.background = '#000';
            if (options.iptv) {
                video.autoplay = true;
                video.muted = true;
            }
            var wrap = document.createElement('div');
            wrap.className = 'player-video-wrap' + (useCanvasBurn ? ' player-video-wrap--burn' : '');
            wrap.appendChild(video);

            var canvasBurn = null;
            var watermarkMotion = null;
            if (useCanvasBurn) {
                var canvas = document.createElement('canvas');
                canvas.className = 'player-video-canvas';
                canvas.setAttribute('aria-label', 'Video player');
                wrap.appendChild(canvas);
            } else if (options.watermark) {
                var watermark = document.createElement('div');
                watermark.className = 'movie-viewer-watermark';
                watermark.textContent = options.watermark;
                wrap.appendChild(watermark);
            }

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

            var seekBar = document.createElement('div');
            seekBar.className = 'player-seek-bar';

            var skipBackBtn = document.createElement('button');
            skipBackBtn.type = 'button';
            skipBackBtn.className = 'player-seek-btn';
            skipBackBtn.textContent = '−10s';

            var seekRange = document.createElement('input');
            seekRange.type = 'range';
            seekRange.className = 'player-seek-range';
            seekRange.value = 0;
            seekRange.min = 0;
            seekRange.max = 100;
            seekRange.step = 0.1;

            var skipFwdBtn = document.createElement('button');
            skipFwdBtn.type = 'button';
            skipFwdBtn.className = 'player-seek-btn';
            skipFwdBtn.textContent = '+10s';

            var timeEl = document.createElement('span');
            timeEl.className = 'player-seek-time';
            timeEl.textContent = '0:00 / 0:00';

            var fsBtn = document.createElement('button');
            fsBtn.type = 'button';
            fsBtn.className = 'player-seek-btn player-fs-btn';
            fsBtn.textContent = '\u26F6';
            fsBtn.setAttribute('aria-label', 'Fullscreen');

            seekBar.appendChild(skipBackBtn);
            seekBar.appendChild(seekRange);
            seekBar.appendChild(skipFwdBtn);
            seekBar.appendChild(timeEl);
            seekBar.appendChild(fsBtn);

            container.innerHTML = '';
            container.appendChild(wrap);
            container.appendChild(seekBar);
            container.appendChild(controls);

            var seeking = false;

            function formatTime(sec) {
                if (!isFinite(sec) || sec < 0) return '0:00';
                var m = Math.floor(sec / 60);
                var s = Math.floor(sec % 60);
                return m + ':' + (s < 10 ? '0' : '') + s;
            }

            function updateSeekUI() {
                var dur = video.duration;
                if (!isFinite(dur) || dur <= 0) {
                    timeEl.textContent = formatTime(video.currentTime) + ' / --:--';
                    return;
                }
                if (!seeking) {
                    seekRange.max = dur;
                    seekRange.value = video.currentTime;
                }
                timeEl.textContent = formatTime(video.currentTime) + ' / ' + formatTime(dur);
            }

            function seekTo(time) {
                var dur = video.duration;
                if (!isFinite(dur) || dur <= 0) return;
                video.currentTime = Math.max(0, Math.min(time, dur));
                updateSeekUI();
            }

            video.addEventListener('timeupdate', updateSeekUI);
            video.addEventListener('loadedmetadata', updateSeekUI);
            video.addEventListener('durationchange', updateSeekUI);

            seekRange.addEventListener('input', function () {
                seeking = true;
                var t = parseFloat(seekRange.value);
                timeEl.textContent = formatTime(t) + ' / ' + formatTime(video.duration);
            });
            seekRange.addEventListener('change', function () {
                seeking = false;
                seekTo(parseFloat(seekRange.value));
            });
            skipBackBtn.addEventListener('click', function () { seekTo(video.currentTime - 10); });
            skipFwdBtn.addEventListener('click', function () { seekTo(video.currentTime + 10); });

            function getFsElement() {
                return document.fullscreenElement || document.webkitFullscreenElement || document.msFullscreenElement || null;
            }

            function requestFs(el) {
                var fn = el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen;
                if (fn) return fn.call(el);
                return Promise.reject();
            }

            function exitFs() {
                var fn = document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen;
                if (fn) return fn.call(document);
                return Promise.resolve();
            }

            function isWrapFullscreen() {
                return getFsElement() === wrap;
            }

            function updateFsButton() {
                fsBtn.textContent = isWrapFullscreen() ? '\u2715' : '\u26F6';
            }

            function updateWatermarkLayout() {
                if (canvasBurn) {
                    canvasBurn.setFontSize(isWrapFullscreen() ? 12 : 10);
                    canvasBurn.syncSize();
                    return;
                }
                var wm = wrap.querySelector('.movie-viewer-watermark');
                if (!wm) return;
                wm.style.fontSize = isWrapFullscreen() ? '12px' : '10px';
                if (watermarkMotion) {
                    watermarkMotion.reposition();
                }
            }

            var fsRedirecting = false;

            function enterWrapFullscreen() {
                var wasPlaying = !video.paused && !video.ended;
                var savedTime = video.currentTime;
                return requestFs(wrap).then(function () {
                    if (savedTime > 0 && isFinite(video.duration)) {
                        video.currentTime = Math.min(savedTime, video.duration);
                    }
                    if (wasPlaying) {
                        video.play().catch(function () {});
                    }
                    updateFsButton();
                    updateWatermarkLayout();
                });
            }

            function onFullscreenChange() {
                if (fsRedirecting) return;
                var fsEl = getFsElement();
                if (fsEl === video) {
                    fsRedirecting = true;
                    exitFs().finally(function () {
                        setTimeout(function () {
                            enterWrapFullscreen().finally(function () {
                                fsRedirecting = false;
                            });
                        }, 50);
                    });
                    return;
                }
                updateFsButton();
                updateWatermarkLayout();
            }

            document.addEventListener('fullscreenchange', onFullscreenChange);
            document.addEventListener('webkitfullscreenchange', onFullscreenChange);
            video.addEventListener('fullscreenchange', onFullscreenChange);
            video.addEventListener('webkitfullscreenchange', onFullscreenChange);

            fsBtn.addEventListener('click', function () {
                if (isWrapFullscreen()) {
                    exitFs();
                } else {
                    enterWrapFullscreen();
                }
            });

            video.addEventListener('dblclick', function (e) {
                e.preventDefault();
                if (isWrapFullscreen()) {
                    exitFs();
                } else {
                    enterWrapFullscreen();
                }
            });

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

            function loadQuality(quality, isAuto, resumeAt) {
                var url = streams[quality];
                if (!url) return;
                currentQuality = quality;
                var resume = (typeof resumeAt === 'number' && resumeAt > 0) ? resumeAt : 0;
                destroyHls();
                video.pause();

                function tryResume() {
                    if (resume > 0 && isFinite(video.duration) && video.duration > 0) {
                        video.currentTime = Math.min(resume, video.duration);
                        resume = 0;
                        updateSeekUI();
                    }
                }

                function tryPlay() {
                    if (!wrap.classList.contains('is-protected')) {
                        video.play().catch(function () {});
                    }
                }

                if (isHls(url) && window.Hls && Hls.isSupported()) {
                    hlsInstance = new Hls({
                        startLevel: -1,
                        capLevelToPlayerSize: true,
                        maxBufferHole: 0.5,
                        enableWorker: true,
                    });
                    hlsInstance.loadSource(url);
                    hlsInstance.attachMedia(video);
                    hlsInstance.on(Hls.Events.MANIFEST_PARSED, function () {
                        tryResume();
                        tryPlay();
                    });
                    hlsInstance.on(Hls.Events.ERROR, function (event, data) {
                        if (!data.fatal) return;
                        statusEl.textContent = 'Stream xatosi';
                        tryPlay();
                    });
                    video.addEventListener('loadedmetadata', tryResume, { once: true });
                } else if (video.canPlayType('application/vnd.apple.mpegurl') && isHls(url)) {
                    video.addEventListener('loadedmetadata', function () {
                        tryResume();
                        tryPlay();
                    }, { once: true });
                    video.src = url;
                } else {
                    video.addEventListener('loadedmetadata', function () {
                        tryResume();
                        tryPlay();
                    }, { once: true });
                    video.src = url;
                }
                updateStatus(quality, isAuto);
            }

            function reloadCurrent() {
                if (!currentQuality) return;
                var t = (video.currentTime && isFinite(video.currentTime)) ? video.currentTime : 0;
                loadQuality(currentQuality, currentMode === 'auto', t);
            }

            setupCaptureProtection(wrap, video, clearVideoSource, reloadCurrent);

            if (options.iptv) {
                video.addEventListener('playing', function () {
                    if (video.muted) {
                        video.muted = false;
                    }
                }, { once: true });
            }

            if (useCanvasBurn) {
                var canvasEl = wrap.querySelector('.player-video-canvas');
                if (canvasEl) {
                    canvasBurn = startCanvasBurn(wrap, video, canvasEl, options.watermark || '', {
                        getBottomPad: function () {
                            return isWrapFullscreen() ? 24 : 12;
                        },
                    });
                }
            } else if (options.watermark) {
                var wmEl = wrap.querySelector('.movie-viewer-watermark');
                if (wmEl) {
                    watermarkMotion = startWatermarkMotion(wrap, wmEl, {
                        getBottomPad: function () {
                            if (isWrapFullscreen()) return 24;
                            return video.controls ? 52 : 12;
                        },
                    });
                }
            }

            function applyMode(mode, resumeAt) {
                currentMode = mode;
                localStorage.setItem('kino_quality_mode', mode);
                if (mode === 'auto') {
                    select.value = 'auto';
                    estimateByProbe(streams, function (detected) {
                        var best = pickBestQuality(streams, detected);
                        loadQuality(best, true, resumeAt);
                    });
                } else {
                    select.value = mode;
                    loadQuality(mode, false, resumeAt);
                }
            }

            select.addEventListener('change', function () {
                var t = (video.currentTime && isFinite(video.currentTime)) ? video.currentTime : 0;
                applyMode(select.value, t);
            });

            if (currentMode !== 'auto' && streams[currentMode]) {
                select.value = currentMode;
                loadQuality(currentMode, false);
            } else if (options.iptv && streams['720']) {
                select.value = '720';
                loadQuality('720', false);
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
