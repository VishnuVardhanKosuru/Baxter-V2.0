export const SAMPLE_FRD = {
  name: "FRD_Baxter_Sigma_Spectrum_Infusion_Pump_v3.4.docx",
  size: "2.4 MB",
  type: "Word Document",
  requirementsCount: 14,
  summary: "Functional Requirements Specification for Baxter Sigma Spectrum Infusion Pump System - Safety Interlocks, Dose Error Reduction System (DERS), and Remote Calibration Protocols."
};

export const SAMPLE_EXCEL = {
  name: "Manual_Test_Cases_Infusion_Module_v1.2.docx",
  size: "840 KB",
  type: "Word Document",
  testCasesCount: 28,
  summary: "Manual Test Suite covering rate setting, air-in-line alarms, occlusion detection, battery backup, and DERS drug library verification."
};

export const GENERATED_TEST_CASES = [
  {
    id: "TC-AUTO-001",
    frdRef: "FRD-SEC-4.1",
    title: "Verify Dose Error Reduction System (DERS) Hard Limits",
    module: "Infusion Safety",
    priority: "Critical",
    manualSteps: 5,
    autoStatus: "Automated",
    scriptName: "ders_safety_limits.spec.ts"
  },
  {
    id: "TC-AUTO-002",
    frdRef: "FRD-ALM-2.3",
    title: "Air-in-Line Sensor Ultrasonic Alarm Detection & Interlock",
    module: "Alarm Systems",
    priority: "High",
    manualSteps: 4,
    autoStatus: "Automated",
    scriptName: "air_in_line_alarm.spec.ts"
  },
  {
    id: "TC-AUTO-003",
    frdRef: "FRD-PWR-1.8",
    title: "Battery Switchover Under High Flow Rate Operation (1000 mL/hr)",
    module: "Power Management",
    priority: "Medium",
    manualSteps: 6,
    autoStatus: "Automated",
    scriptName: "battery_switchover.spec.ts"
  },
  {
    id: "TC-AUTO-004",
    frdRef: "FRD-CAL-5.0",
    title: "Remote Telemetry Calibration & Syringe Size Auto-Detect",
    module: "Calibration",
    priority: "High",
    manualSteps: 7,
    autoStatus: "Automated",
    scriptName: "syringe_detect_cal.spec.ts"
  },
  {
    id: "TC-AUTO-005",
    frdRef: "FRD-GUI-3.2",
    title: "Touchscreen Lockout During Rapid Rate Infusion",
    module: "User Interface",
    priority: "Medium",
    manualSteps: 3,
    autoStatus: "Automated",
    scriptName: "touchscreen_lockout.spec.ts"
  }
];

export const MOCK_AUTOMATED_SCRIPT_CONTENT = `/**
 * Baxter Test Automation Engine - Generated Automated Test Script
 * Target Framework: Playwright / TypeScript
 * Source FRD: FRD_Baxter_Sigma_Spectrum_Infusion_Pump_v3.4.pdf
 * Source Excel: Manual_Test_Cases_Infusion_Module_v1.2.xlsx
 * Generated On: ${new Date().toISOString()}
 */

import { test, expect } from '@playwright/test';

test.describe('Baxter Sigma Spectrum - Safety & DERS Automated Suite', () => {

  test.beforeEach(async ({ page }) => {
    // Initialize Baxter Medical Interface Mock Console
    await page.goto('https://pump-control.baxter.com');
    await page.click('button#auth-device-session');
  });

  test('TC-AUTO-001: Verify DERS Hard Limits Validation', async ({ page }) => {
    // Step 1: Select Infusion Mode & Drug Library
    await page.selectOption('#drug-library-select', 'HEPARIN_STANDARD');
    
    // Step 2: Input Dosage exceeding Upper Hard Limit (50,000 units/hr)
    await page.fill('#infusion-rate-input', '65000');
    await page.click('#confirm-dose-btn');

    // Step 3: Verify Baxter Safety Interlock Warning Banner
    const warningAlert = page.locator('#ders-hard-limit-alert');
    await expect(warningAlert).toBeVisible();
    await expect(warningAlert).toContainText('DOSE EXCEEDS HARD LIMIT (50,000 U/hr)');
    
    // Step 4: Verify Pump Start Button is Disabled
    const startButton = page.locator('#start-infusion-btn');
    await expect(startButton).toBeDisabled();
  });

  test('TC-AUTO-002: Air-In-Line Sensor Alarm Interlock', async ({ page }) => {
    // Step 1: Prime tubing and initiate flow at 150 mL/hr
    await page.fill('#flow-rate-input', '150');
    await page.click('#start-infusion-btn');
    
    // Step 2: Simulate Air Bubble trigger (50 microliters)
    await page.evaluate(() => window.baxterHardware.triggerAirInLine(50));

    // Step 3: Assert High-Priority Audible & Visual Alarm
    const alarmBanner = page.locator('#alarm-banner-air-in-line');
    await expect(alarmBanner).toHaveClass(/alarm-critical/);
    
    // Step 4: Assert Mechanical Clamp Valve state is CLOSED
    const valveStatus = await page.getAttribute('#clamp-valve', 'data-state');
    expect(valveStatus).toBe('CLOSED');
  });

});
`;
