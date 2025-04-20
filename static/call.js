let ws, mediaRecorder, mediaStream;
let audioContext = new AudioContext();
let analyser, sourceNode, animationId;
let sessionId = crypto.randomUUID();

// Audio queue management
let audioQueue = [];
let isPlaying = false;
let minBufferSize = 2;  // Minimum number of chunks to buffer before playback

const startBtn = document.getElementById("start-call");
const stopBtn = document.getElementById("stop-call");
const transcriptEl = document.getElementById("transcript");
const statusEl = document.getElementById("call-status");
const micGlow = document.getElementById("mic-glow");
const canvas = document.getElementById("waveform");
const ctx = canvas.getContext("2d");
const voiceSelect = document.getElementById("voice-select");

function updateVoiceSelection(voice) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: "session.update",
            session: {
                voice: voice
            }
        }));
    }
}

voiceSelect.onchange = () => {
    updateVoiceSelection(voiceSelect.value);
};

function setupAnalyser(stream) {
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    sourceNode = audioContext.createMediaStreamSource(stream);
    sourceNode.connect(analyser);
    canvas.classList.add('active');
    drawWaveform();
}

function drawWaveform() {
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    function draw() {
        animationId = requestAnimationFrame(draw);
        analyser.getByteFrequencyData(dataArray);

        ctx.fillStyle = "#121212";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        const barWidth = (canvas.width / bufferLength) * 2;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
            const barHeight = dataArray[i] / 2;
            
            // Create gradient for bars
            const gradient = ctx.createLinearGradient(0, canvas.height, 0, canvas.height - barHeight);
            gradient.addColorStop(0, 'rgba(50,150,255,0.8)');
            gradient.addColorStop(1, 'rgba(50,150,255,0.2)');
            
            ctx.fillStyle = gradient;
            ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
            x += barWidth + 1;
        }
    }

    draw();
}

function cleanupAudio() {
    if (animationId) cancelAnimationFrame(animationId);
    if (sourceNode) sourceNode.disconnect();
    if (canvas) {
        canvas.classList.remove('active');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
}

// Function to handle audio playback from queue
async function playNextBuffer() {
    if (audioQueue.length === 0) {
        isPlaying = false;
        return;
    }

    isPlaying = true;
    const buffer = audioQueue.shift();
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext.destination);
    
    // Chain to next buffer when this one ends
    source.onended = () => {
        playNextBuffer();
    };
    
    source.start();
}

startBtn.onclick = async () => {
    try {
        // Reset audio queue state
        audioQueue = [];
        isPlaying = false;

        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(mediaStream, {
            mimeType: "audio/webm;codecs=opus",
            audioBitsPerSecond: 64000,
        });

        ws = new WebSocket(`ws://localhost:8000/api/v1/call/${sessionId}`);
        statusEl.textContent = "Connecting...";

        ws.onopen = () => {
            statusEl.textContent = "Streaming...";
            mediaRecorder.start(500);
            setupAnalyser(mediaStream);
            
            // Configure VAD settings
            ws.send(JSON.stringify({
                type: "session.update",
                session: {
                    turn_detection: {
                        type: "server_vad",
                        threshold: 0.5,
                        silence_duration_ms: 500,
                        prefix_padding_ms: 200,
                        create_response: false,
                        interrupt_response: false
                    }
                }
            }));
            
            // Set initial voice
            updateVoiceSelection(voiceSelect.value);
        };

        mediaRecorder.ondataavailable = (e) => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(e.data);
            }
        };

        ws.onmessage = async (event) => {
            if (event.data instanceof Blob) {
                const arrayBuffer = await event.data.arrayBuffer();
                const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
                
                // Add to queue
                audioQueue.push(audioBuffer);

                // Start playback if we have enough buffers and not already playing
                if (!isPlaying && audioQueue.length >= minBufferSize) {
                    playNextBuffer();
                }
            } else {
                const msg = JSON.parse(event.data);

                if (msg.type === "session.created") {
                    console.log("Session created:", msg.session);
                }

                if (msg.type === "session.updated") {
                    console.log("Session updated:", msg.session);
                }

                if (msg.type === "input_audio_buffer.speech_started") {
                    micGlow.hidden = false;
                    // Reset audio queue when user starts speaking
                    audioQueue = [];
                    isPlaying = false;
                }

                if (msg.type === "input_audio_buffer.speech_stopped") {
                    micGlow.hidden = true;
                }

                if (msg.type === "transcription") {
                    transcriptEl.textContent = msg.text;
                }

                if (msg.type === "error") {
                    statusEl.textContent = `Error: ${msg.message}`;
                }
            }
        };

        ws.onclose = () => {
            statusEl.textContent = "Disconnected";
            micGlow.hidden = true;
            cleanupAudio();
            voiceSelect.disabled = false;
            // Clear audio queue on disconnect
            audioQueue = [];
            isPlaying = false;
        };

        startBtn.disabled = true;
        stopBtn.disabled = false;
        voiceSelect.disabled = false;
    } catch (err) {
        console.error("Mic error:", err);
        statusEl.textContent = "Mic access denied";
        micGlow.hidden = true;
        cleanupAudio();
        voiceSelect.disabled = false;
    }
};

stopBtn.onclick = () => {
    if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
    if (mediaStream) mediaStream.getTracks().forEach((t) => t.stop());
    if (ws) ws.close(1000, "User stopped session");

    // Clear audio queue on stop
    audioQueue = [];
    isPlaying = false;

    startBtn.disabled = false;
    stopBtn.disabled = true;
    statusEl.textContent = "Idle";
    micGlow.hidden = true;
    cleanupAudio();
    voiceSelect.disabled = false;
}; 