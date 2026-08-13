// Mock dataset for Jira Releases 1 through 10 (5 FRDs and 5 Manual Test Cases per release)
export const JIRA_RELEASES_DATA = Array.from({ length: 10 }, (_, i) => {
  const releaseNum = i + 1;
  
  // Generate 5 FRDs per release
  const frds = Array.from({ length: 5 }, (_, idx) => {
    const itemNum = idx + 1;
    return {
      id: `FRD-${releaseNum}-${itemNum}`,
      key: `JIRA-FRD-${releaseNum}-${itemNum}`,
      title: `R${releaseNum} - FRD Specification Module ${itemNum}`,
      reqCount: 10 + (itemNum % 15),
      status: itemNum % 3 === 0 ? 'In Review' : 'Approved',
      lastUpdated: '2026-08-12',
      author: 'Baxter QA Engineering'
    };
  });

  // Generate 5 Manual Test Cases per release
  const manualTestCases = Array.from({ length: 5 }, (_, idx) => {
    const itemNum = idx + 1;
    return {
      id: `TC-${releaseNum}-${itemNum}`,
      key: `JIRA-TC-${releaseNum}-${itemNum}`,
      title: `R${releaseNum} - Manual Test Case Suite ${itemNum}`,
      tcCount: 15 + (itemNum % 20),
      priority: itemNum % 2 === 0 ? 'High' : 'Medium',
      status: 'Ready for Automation'
    };
  });

  return {
    id: `rel-${releaseNum}`,
    name: `Release ${releaseNum}`,
    version: `v${releaseNum}.0.0`,
    frds,
    manualTestCases
  };
});
