/* ═══════════════════════════════════════════════════════════════
   JARVIS-OS Background Canvas — Particle network + HUD elements
   ═══════════════════════════════════════════════════════════════ */

(function() {
    const canvas = document.getElementById('bg-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let width, height;
    let particles = [];
    let mouse = { x: -1000, y: -1000 };
    const PARTICLE_COUNT = 80;
    const CONNECTION_DIST = 150;
    const MOUSE_DIST = 200;

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    }

    function createParticles() {
        particles = [];
        for (let i = 0; i < PARTICLE_COUNT; i++) {
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                size: Math.random() * 2 + 0.5,
                opacity: Math.random() * 0.5 + 0.2,
            });
        }
    }

    function drawHUDCircle(x, y, radius, rotation) {
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(rotation);
        ctx.strokeStyle = 'rgba(0, 212, 255, 0.08)';
        ctx.lineWidth = 1;

        // Arc segments
        for (let i = 0; i < 4; i++) {
            ctx.beginPath();
            ctx.arc(0, 0, radius, (i * Math.PI / 2) + 0.1, (i * Math.PI / 2) + 1.2);
            ctx.stroke();
        }

        // Tick marks
        ctx.strokeStyle = 'rgba(0, 212, 255, 0.05)';
        for (let i = 0; i < 36; i++) {
            const angle = (i * Math.PI * 2) / 36;
            const inner = radius - 5;
            const outer = radius + 2;
            ctx.beginPath();
            ctx.moveTo(Math.cos(angle) * inner, Math.sin(angle) * inner);
            ctx.lineTo(Math.cos(angle) * outer, Math.sin(angle) * outer);
            ctx.stroke();
        }

        ctx.restore();
    }

    let rotation = 0;

    function animate() {
        ctx.clearRect(0, 0, width, height);
        rotation += 0.002;

        // Draw HUD circles
        drawHUDCircle(width * 0.85, height * 0.15, 80, rotation);
        drawHUDCircle(width * 0.85, height * 0.15, 120, -rotation * 0.7);
        drawHUDCircle(width * 0.15, height * 0.85, 60, rotation * 1.2);

        // Update and draw particles
        particles.forEach((p, i) => {
            p.x += p.vx;
            p.y += p.vy;

            // Wrap around edges
            if (p.x < 0) p.x = width;
            if (p.x > width) p.x = 0;
            if (p.y < 0) p.y = height;
            if (p.y > height) p.y = 0;

            // Mouse interaction
            const dx = mouse.x - p.x;
            const dy = mouse.y - p.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < MOUSE_DIST) {
                const force = (MOUSE_DIST - dist) / MOUSE_DIST;
                p.vx -= (dx / dist) * force * 0.02;
                p.vy -= (dy / dist) * force * 0.02;
            }

            // Damping
            p.vx *= 0.99;
            p.vy *= 0.99;

            // Draw particle
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(0, 212, 255, ${p.opacity})`;
            ctx.fill();

            // Draw connections
            for (let j = i + 1; j < particles.length; j++) {
                const p2 = particles[j];
                const cdx = p.x - p2.x;
                const cdy = p.y - p2.y;
                const cdist = Math.sqrt(cdx * cdx + cdy * cdy);
                if (cdist < CONNECTION_DIST) {
                    const alpha = (1 - cdist / CONNECTION_DIST) * 0.15;
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.strokeStyle = `rgba(0, 212, 255, ${alpha})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        });

        requestAnimationFrame(animate);
    }

    window.addEventListener('resize', () => {
        resize();
    });

    document.addEventListener('mousemove', (e) => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    });

    resize();
    createParticles();
    animate();
})();
