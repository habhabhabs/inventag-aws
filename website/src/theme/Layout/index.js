import React from 'react';
import Layout from '@theme-original/Layout';
import { useEffect } from 'react';

export default function LayoutWrapper(props) {
  useEffect(() => {
    // Get current version dynamically
    const getCurrentVersion = async () => {
      try {
        const response = await fetch('/inventag-aws/version.json');
        const data = await response.json();
        return `v${data.version}`;
      } catch (error) {
        // Try relative path as fallback
        try {
          const fallbackResponse = await fetch('../version.json');
          const fallbackData = await fallbackResponse.json();
          return `v${fallbackData.version}`;
        } catch (fallbackError) {
          // Try alternative paths
          try {
            const altResponse = await fetch('./version.json');
            const altData = await altResponse.json();
            return `v${altData.version}`;
          } catch (altError) {
            return 'Current'; // generic fallback if all paths fail
          }
        }
      }
    };

    // Replace "current" text in sidebar with actual version number
    const replaceVersionText = async () => {
      const currentVersion = await getCurrentVersion();
      
      // Target sidebar menu links that contain "current"
      const menuLinks = document.querySelectorAll('.menu__link');
      menuLinks.forEach(link => {
        if (link.textContent.trim() === 'current') {
          link.textContent = `${currentVersion} (Current)`;
        }
      });
      
      // Also target version switcher dropdown
      const versionSwitcher = document.querySelectorAll('.menu__link--sublist-caret');
      versionSwitcher.forEach(link => {
        if (link.textContent.trim() === 'current' || link.textContent.includes('current')) {
          link.textContent = `${currentVersion} (Current)`;
        }
      });
    };

    // Run immediately and after a short delay
    replaceVersionText();
    setTimeout(replaceVersionText, 500);
    
    // Run after navigation changes
    const observer = new MutationObserver(() => {
      setTimeout(replaceVersionText, 100);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    
    return () => observer.disconnect();
  }, []);

  return <Layout {...props} />;
}