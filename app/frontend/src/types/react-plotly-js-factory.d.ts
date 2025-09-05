// Minimal type declaration to satisfy TypeScript for the factory import
declare module 'react-plotly.js/factory' {
  const createPlotlyComponent: (plotly: any) => any
  export default createPlotlyComponent
}
