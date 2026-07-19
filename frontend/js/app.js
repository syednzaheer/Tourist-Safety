/**
 * Shared frontend logic - sidebar nav, toast notifications, language switch.
 * Loaded on every page. Nothing here talks to the backend; the pages that
 * actually call the API (form.html, map.html, sos.html, dbpolice.html)
 * have their own fetch calls inline.
 */

/* =========================================
   1. NAVIGATION Logic
   ========================================= */
const ui = {
    sidebar: document.getElementById("mySidebar"),
    main: document.getElementById("main"),
    
    openNav: () => {
        ui.sidebar.style.width = "280px";
        // On mobile, maybe don't push main content, overlay it?
        // For now, keeping original push behavior but smoother
        if(window.innerWidth > 768) {
             ui.main.style.marginLeft = "280px";
        }
    },
    
    closeNav: () => {
        ui.sidebar.style.width = "0";
        ui.main.style.marginLeft = "0";
    }
};

// Expose to window for onclick handlers (legacy support)
window.openNav = ui.openNav;
window.closeNav = ui.closeNav;


/* =========================================
   2. TOAST NOTIFICATION SYSTEM (Replaces alert)
   ========================================= */
const toaster = {
    init: () => {
        // Create container if not exists
        if (!document.querySelector('.toast-container')) {
            const container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
    },

    show: (message, type = 'info') => {
        toaster.init();
        const container = document.querySelector('.toast-container');
        
        // Create Toast Element
        const toast = document.createElement('div');
        toast.className = `toast-message ${type}`;
        
        // Icon based on type
        const icons = {
            'success': '✅',
            'error': '❌',
            'info': 'ℹ️',
            'warning': '⚠️'
        };

        toast.innerHTML = `
            <span style="font-size: 1.2rem; margin-right: 12px;">${icons[type] || '✨'}</span>
            <span>${message}</span>
        `;

        container.appendChild(toast);

        // trigger animation next frame so the CSS transition actually fires
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });

        // auto dismiss
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 400); // Wait for transition
        }, 12000); // 12 seconds
    }
};

// Override native alert globally for instant upgrade
window.alert = (msg) => toaster.show(msg, 'info');


/* =========================================
   3. TRANSLATION & DYNAMIC CONTENT
   ========================================= */
const translations = {
    en: {
        mainTitle: "Smart Tourist Safety System",
        mainDesc: "A Smart Prototype by Neural Nexus for SIH 2025 (Problem ID: 25002).",
        howTitle: "How This Works",
        footer: "Tourist Safety System 2025 | Neural Nexus",
        steps: [
            "Get a digital ID when you arrive in the locality.",
            "Check the map to see which areas are safe or risky.",
            "If something goes wrong, hit the SOS button to get help."
        ]
    },
    hi: {
        mainTitle: "स्मार्ट टूरिस्ट सुरक्षा प्रणाली",
        mainDesc: "छात्र प्रोटोटाइप - हैदराबाद (SIH25002).",
        howTitle: "यह कैसे काम करता है",
        footer: "पर्यटक सुरक्षा प्रणाली 2025 | न्यूरल नेक्सस",
        steps: [
            "कतार में डिजिटल आईडी प्राप्त करें।",
            "मानचित्र देखें कि कौन से क्षेत्र सुरक्षित या जोखिमपूर्ण हैं।",
            "अगर कुछ गलत हो, तो मदद पाने के लिए SOS दबाएँ।"
        ]
    }
};

function initTranslations() {
    const langSelect = document.getElementById('langSelect');
    if(!langSelect) return;

    langSelect.addEventListener('change', function () {
        const t = translations[this.value];
        if(!t) return;

        // Safely update specific elements
        const setText = (id, text) => {
            const el = document.getElementById(id);
            if(el) el.innerText = text;
        };

        setText('mainTitle', t.mainTitle);
        setText('mainDesc', t.mainDesc);
        setText('howTitle', t.howTitle);
        setText('footerText', t.footer);

        document.querySelectorAll(".step-text").forEach((el, i) => {
            if(t.steps[i]) el.innerText = t.steps[i];
        });

        // User Feedback
        toaster.show(`Language switched to ${this.options[this.selectedIndex].text}`, 'success');
    });
}


// Initialization
document.addEventListener('DOMContentLoaded', () => {
    initTranslations();
});
