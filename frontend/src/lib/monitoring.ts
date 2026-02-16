/**
 * Application Insights monitoring configuration for the frontend.
 */

import { ApplicationInsights } from '@microsoft/applicationinsights-web';

let appInsights: ApplicationInsights | null = null;

/**
 * Initialize Application Insights monitoring.
 * Only initializes if NEXT_PUBLIC_APPLICATIONINSIGHTS_CONNECTION_STRING is set.
 */
export function initializeMonitoring(): void {
  const connectionString = process.env.NEXT_PUBLIC_APPLICATIONINSIGHTS_CONNECTION_STRING;

  if (!connectionString) {
    // Skip initialization in local development when connection string is not set
    return;
  }

  appInsights = new ApplicationInsights({
    config: {
      connectionString,
    },
  });

  appInsights.loadAppInsights();
  appInsights.trackPageView();
}

/**
 * Get the Application Insights instance (if initialized).
 */
export function getAppInsights(): ApplicationInsights | null {
  return appInsights;
}
