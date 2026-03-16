interface Props {
  temperature: number;
  maxTokens: number;
  onTemperatureChange: (v: number) => void;
  onMaxTokensChange: (v: number) => void;
  supportsTemperature: boolean;
  supportsMaxTokens: boolean;
}

export default function RuntimeOptions({
  temperature,
  maxTokens,
  onTemperatureChange,
  onMaxTokensChange,
  supportsTemperature,
  supportsMaxTokens,
}: Props) {
  return (
    <div className="runtime-options">
      {supportsTemperature && (
        <label>
          <span>Temperature: {temperature.toFixed(1)}</span>
          <input
            type="range"
            min="0"
            max="2"
            step="0.1"
            value={temperature}
            onChange={(e) => onTemperatureChange(parseFloat(e.target.value))}
          />
        </label>
      )}
      {supportsMaxTokens && (
        <label>
          <span>Max tokens: {maxTokens}</span>
          <input
            type="number"
            min="64"
            max="32768"
            step="64"
            value={maxTokens}
            onChange={(e) => onMaxTokensChange(parseInt(e.target.value) || 2048)}
          />
        </label>
      )}
    </div>
  );
}
