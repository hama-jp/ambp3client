/**
 * AMB P3 Real-time Dashboard
 * リアルタイムラップタイマー with 音声読み上げ
 */

class LapTimerApp {
    constructor() {
        this.websocket = null;
        this.selectedTransponder = null;
        this.voiceEnabled = true;
        this.speechSynthesis = window.speechSynthesis;

        // DOM Elements
        this.elements = {
            transponderSelect: document.getElementById('transponderSelect'),
            dashboard: document.getElementById('dashboard'),
            connectionStatus: document.getElementById('connectionStatus'),
            statusText: document.getElementById('statusText'),
            currentTransponderId: document.getElementById('currentTransponderId'),
            transponderName: document.getElementById('transponderName'),
            totalLaps: document.getElementById('totalLaps'),
            bestLap: document.getElementById('bestLap'),
            averageLap: document.getElementById('averageLap'),
            latestLap: document.getElementById('latestLap'),
            latestLapCard: document.getElementById('latestLapCard'),
            lastUpdate: document.getElementById('lastUpdate'),
            voiceToggle: document.getElementById('voiceToggle'),
            voiceIcon: document.getElementById('voiceIcon'),
            voiceText: document.getElementById('voiceText')
        };

        this.init();
    }

    /**
     * Initialize application
     */
    async init() {
        console.log('Initializing AMB Lap Timer Dashboard...');

        // Load transponders
        await this.loadTransponders();

        // Setup event listeners
        this.setupEventListeners();

        // Connect WebSocket
        this.connectWebSocket();
    }

    /**
     * Load available transponders
     */
    async loadTransponders() {
        try {
            const response = await fetch('/api/transponders');
            const transponders = await response.json();

            console.log('Loaded transponders:', transponders);

            // Clear existing options (except first)
            this.elements.transponderSelect.innerHTML = '<option value="">選択してください</option>';

            // Add transponder options
            transponders.forEach(trans => {
                const option = document.createElement('option');
                option.value = trans.transponder_id;

                if (trans.name && trans.kart_number) {
                    option.textContent = `#${trans.kart_number} - ${trans.name} (ID: ${trans.transponder_id})`;
                } else if (trans.kart_number) {
                    option.textContent = `#${trans.kart_number} (ID: ${trans.transponder_id})`;
                } else {
                    option.textContent = `トランスポンダー ${trans.transponder_id}`;
                }

                this.elements.transponderSelect.appendChild(option);
            });

        } catch (error) {
            console.error('Failed to load transponders:', error);
            this.showError('トランスポンダーの読み込みに失敗しました');
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Transponder selection
        this.elements.transponderSelect.addEventListener('change', (e) => {
            const transponderId = e.target.value;
            if (transponderId) {
                this.selectTransponder(parseInt(transponderId));
            } else {
                this.elements.dashboard.style.display = 'none';
            }
        });

        // Voice toggle
        this.elements.voiceToggle.addEventListener('click', () => {
            this.toggleVoice();
        });
    }

    /**
     * Select transponder and load data
     */
    async selectTransponder(transponderId) {
        console.log('Selected transponder:', transponderId);

        this.selectedTransponder = transponderId;

        // Show dashboard
        this.elements.dashboard.style.display = 'block';
        this.elements.currentTransponderId.textContent = transponderId;

        // Load initial data
        await this.loadLapStats(transponderId);
    }

    /**
     * Load lap statistics for transponder
     */
    async loadLapStats(transponderId) {
        try {
            const response = await fetch(`/api/laps/${transponderId}`);
            const stats = await response.json();

            console.log('Lap stats:', stats);

            this.updateDashboard(stats);

        } catch (error) {
            console.error('Failed to load lap stats:', error);
            this.showError('ラップデータの読み込みに失敗しました');
        }
    }

    /**
     * Update dashboard with stats
     */
    updateDashboard(stats) {
        // Total laps
        this.elements.totalLaps.textContent = stats.total_laps;

        // Best lap
        if (stats.best_lap !== null) {
            this.elements.bestLap.textContent = this.formatLapTime(stats.best_lap);
        } else {
            this.elements.bestLap.textContent = '--:--';
        }

        // Average lap
        if (stats.average_lap !== null) {
            this.elements.averageLap.textContent = this.formatLapTime(stats.average_lap);
        } else {
            this.elements.averageLap.textContent = '--:--';
        }

        // Latest lap
        if (stats.latest_lap !== null) {
            this.elements.latestLap.textContent = this.formatLapTime(stats.latest_lap);
        } else {
            this.elements.latestLap.textContent = '--:--';
        }

        // Last update
        this.updateLastUpdateTime();
    }

    /**
     * Format lap time from seconds to MM:SS.mmm
     */
    formatLapTime(seconds) {
        if (!seconds || seconds <= 0) {
            return '--:--';
        }

        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;

        return `${minutes}:${secs.toFixed(3).padStart(6, '0')}`;
    }

    /**
     * Connect to WebSocket
     */
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        console.log('Connecting to WebSocket:', wsUrl);

        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus(true);
        };

        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus(false);
        };

        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus(false);

            // Reconnect after 3 seconds
            setTimeout(() => {
                console.log('Reconnecting WebSocket...');
                this.connectWebSocket();
            }, 3000);
        };
    }

    /**
     * Handle incoming WebSocket messages
     */
    handleWebSocketMessage(data) {
        console.log('WebSocket message:', data);

        if (data.type === 'new_lap') {
            // Check if this lap is for the selected transponder
            if (this.selectedTransponder && data.transponder_id === this.selectedTransponder) {
                // Update dashboard
                this.updateDashboard(data.stats);

                // Highlight latest lap card
                this.elements.latestLapCard.classList.add('new-lap');
                setTimeout(() => {
                    this.elements.latestLapCard.classList.remove('new-lap');
                }, 1000);

                // Voice announcement
                if (this.voiceEnabled && data.lap_time) {
                    this.speakLapTime(data.lap_time);
                }
            }
        }
    }

    /**
     * Speak lap time using Web Speech API
     */
    speakLapTime(lapTime) {
        if (!this.speechSynthesis || !this.voiceEnabled) {
            return;
        }

        // Cancel any ongoing speech
        this.speechSynthesis.cancel();

        // Format time for speech (e.g., "1分23秒456")
        const minutes = Math.floor(lapTime / 60);
        const seconds = Math.floor(lapTime % 60);
        const milliseconds = Math.floor((lapTime % 1) * 1000);

        let speechText = '';
        if (minutes > 0) {
            speechText += `${minutes}分`;
        }
        speechText += `${seconds}秒${milliseconds}`;

        console.log('Speaking:', speechText);

        const utterance = new SpeechSynthesisUtterance(speechText);
        utterance.lang = 'ja-JP';
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        this.speechSynthesis.speak(utterance);
    }

    /**
     * Toggle voice announcements
     */
    toggleVoice() {
        this.voiceEnabled = !this.voiceEnabled;

        if (this.voiceEnabled) {
            this.elements.voiceIcon.textContent = '🔊';
            this.elements.voiceText.textContent = '音声ON';
            this.elements.voiceToggle.classList.remove('disabled');
            console.log('Voice enabled');
        } else {
            this.elements.voiceIcon.textContent = '🔇';
            this.elements.voiceText.textContent = '音声OFF';
            this.elements.voiceToggle.classList.add('disabled');
            this.speechSynthesis.cancel();
            console.log('Voice disabled');
        }
    }

    /**
     * Update connection status indicator
     */
    updateConnectionStatus(connected) {
        const statusDot = this.elements.connectionStatus.querySelector('.status-dot');

        if (connected) {
            statusDot.classList.remove('offline');
            statusDot.classList.add('online');
            this.elements.statusText.textContent = '接続済み';
        } else {
            statusDot.classList.remove('online');
            statusDot.classList.add('offline');
            this.elements.statusText.textContent = '未接続';
        }
    }

    /**
     * Update last update time
     */
    updateLastUpdateTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('ja-JP', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        this.elements.lastUpdate.textContent = timeString;
    }

    /**
     * Show error message
     */
    showError(message) {
        console.error(message);
        // Could add toast notification here
        alert(message);
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.lapTimerApp = new LapTimerApp();
});
