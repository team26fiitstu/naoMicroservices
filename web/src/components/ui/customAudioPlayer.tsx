import { useRef, useState, useEffect, useCallback } from 'react';
import { audioBufferToWebMBlob } from "./webmAudio";
import { standardButtonColor, standardButtonHeight, secondaryButtonColor} from "@/components/styles/styles";
import { Button } from "@/components/ui/button";
import { Trash2, Loader2, Pickaxe, ArrowRight } from "lucide-react";

const NO_NAMING = true; 
// ── API config ────────────────────────────────────────────────────
const TO_TEXT_API = NO_NAMING? "http://localhost:9901" : "";

console.log(process.env.HOST_DOCKER_INTERNAL);
console.log(process.env);
export function CustomAudioPlayer({url, keyID, index, blob, defaultText,
                            overallRecordedMessage, onOverallRecordedMessageChange, 
                            saveAudioFile, languageVoice, speedVoice, aggregatedVoiceLinesRef}) {
  const playerRef = useRef<any>(null);
  const textFromVideoTextareaRef = useRef<any>(null);
  const audioRef = useRef(null);
  const [duration, setDuration] = useState(0.0);
  const [audioPlayer, setAudioPlayer] = useState({"url": url,"blob": blob});
  const [textAreaText, setTextAreaText] = useState(defaultText? defaultText: "Text to be said by NAO. Possibly loaded from video.");
  const [waitBefore, setWaitBefore] = useState(0);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [extracting, setExtracting] = useState<string | null>(null);

  useEffect((): string => {
    async function endTime(blob) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioContext();
      const arrayBuffer = await blob.arrayBuffer();
      const result = await audioCtx.decodeAudioData(arrayBuffer);
      setDuration(result.duration);
      return result.duration.toString();
    }
    endTime(blob);
  }, [blob, duration]);

  useEffect(() => {
    if (playerRef.current) {
      playerRef.current.load(); // Force browser to load new file
      playerRef.current.play().catch(err => console.log("Playback blocked:", err));
    }
  }, [audioPlayer]); 


  const handlePlay = () => {
    playerRef.current?.play();
  };

  const handlePause = () => {
    playerRef.current?.pause();
  };

  const handleStop = () => {
    playerRef.current?.stop();
  };

  const handleFocus = () => {
    playerRef.current?.focus();
  };

  const endTime = async (blob): string => {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    const audioCtx = new AudioContext();
    const arrayBuffer = await blob.arrayBuffer();
    const result = await audioCtx.decodeAudioData(arrayBuffer);
    return result.duration.toString();
  }

  async function clipAudioBufferInWebmFormat(audioContext, audioBuffer, startSec, endSec) {
        const fullBuffer = await audioContext.decodeAudioData(audioBuffer);

        const duration = fullBuffer.duration;
        const sampleRate = fullBuffer.sampleRate;
        const numChannels = fullBuffer.numberOfChannels;

        const actualStart = Math.max(0, Math.min(startSec, duration));
        const actualEnd = Math.max(actualStart, Math.min(endSec, duration));

        const startOffset = Math.floor(actualStart * sampleRate);
        const endOffset = Math.floor(actualEnd * sampleRate);
        const frameCount = endOffset - startOffset;

        const clippedBuffer = audioContext.createBuffer(numChannels, frameCount, sampleRate);

        for (let channel = 0; channel < numChannels; channel++) {
            const originalChannelData = fullBuffer.getChannelData(channel);
            const clippedChannelData = clippedBuffer.getChannelData(channel);
            
            const slicedData = originalChannelData.subarray(startOffset, endOffset);
            clippedChannelData.set(slicedData);
        }

        return clippedBuffer;
    }

  function handleClip(event): void {
      event.preventDefault();
      const form = event.target;
      const formData = new FormData(form);
      const startInterval = formData.get("startInterval");
      const endInterval = formData.get("endInterval");

      blob.arrayBuffer()
          .then((arrayBuffer) => {
              const audioCtx = new AudioContext();
              clipAudioBufferInWebmFormat(audioCtx, arrayBuffer, startInterval, endInterval).then(
                (clippedBuffer) => {
                  console.log(clippedBuffer);
                    audioBufferToWebMBlob(audioCtx, clippedBuffer).then((blob) => {
                        const url = window.URL.createObjectURL(blob);
           
                        setAudioPlayer(url, blob);
                        audioPlayer.url = url;
                        audioPlayer.blob = blob;
                        playerRef.src = url;
                        playerRef.current.innerHTML = "<source src=\"" + url + "\" type=\"audio/webm\"/>";
                        playerRef.current?.pause();
                        playerRef.current?.load();
                        playerRef.current?.play();
                    });
                });
          });
  }

  

  const extractFromVideo = async () => {
      const audioBlob = audioPlayer.blob;
     // const audioFile = await fetch(audioPlayer.url);
      const reader = new FileReader();
      reader.readAsDataURL(audioBlob);
      reader.onloadend = async () => {
        try {
            const audioInBase64 = reader.result.replaceAll("data:audio/*;base64,","");
            console.log({ "audio_file": audioInBase64, "lang": languageVoice, "speed": speedVoice, "model": "large-v1" });
            const res = await fetch(`${TO_TEXT_API}/translate/webm`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json"
              },
              body: JSON.stringify({ "audio_file": audioInBase64, "lang": languageVoice, "speed": speedVoice, "model": "large-v1" }),
            });
            if (!res.ok) throw new Error(`Upload failed: HTTP ${res.status}`);
            const data = await res.json();
            const translation: string = data.translation;
            setTextAreaText(translation);
            textFromVideoTextareaRef.current.value = translation;
            console.log(translation);

            if (overallRecordedMessage["voice_lines_configs"] === undefined) {
                overallRecordedMessage["voice_lines_configs"] = {};
            }
            const fileName = keyID + ".webm";
            overallRecordedMessage["voice_lines_configs"][(index + "").padStart(3, "0")] = 
                {"translation": translation, "index": index, "fileName": fileName};
            saveAudioFile(audioInBase64, fileName, languageVoice, speedVoice);
            overallRecordedMessage["extractedText"] = translation;
            
            onOverallRecordedMessageChange(overallRecordedMessage);
        } catch (err) {
          console.log(err);
          //showStatus("error", err instanceof Error ? err.message : "Odstránenie zlyhalo");
        } finally {
          setExtracting(null);
        }
      }
  }

  const extendValueFromTextAreas = () => {
    aggregatedVoiceLinesRef.current.value += textFromVideoTextareaRef.current.value;
  }

  // ── delete recorded voice line if saved ──────────────────────────────────────────────
  // DELETE /exercise/<id>/frame/<idx>
  const onDelete = useCallback(async () => {
    if (!audioRef) return;
    audioRef.current.remove();
    if (!keyID) return;
    setDeleting(frameIdx);
    try {
      const res = await fetch(`${EDITOR_API}/exercise/${keyID}/frame/${frameIdx}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // showStatus("success", "Snímka odstránená.");
    } catch (err) {
      //showStatus("error", err instanceof Error ? err.message : "Odstránenie zlyhalo");
    } finally {
      ReactDOM.unmountComponentAtNode(ReactDOM.findDOMNode(this).parentNode);
      setDeleting(null);
    }
  }, [keyID, index]);

  const processWaitBeforeChange = (value) => {
    setWaitBefore(value);
    overallRecordedMessage["voice_lines_configs"][(index + "").padStart(3, "0")]["wait"] = value;
  }

  return (
    <div ref={audioRef} style={{margin: "1.5rem 0 1.5rem 0", backgroundImage: "url(/voiceLine.svg)", backgroundBlendMode: "luminosity", backgroundSize: "350px", backgroundPositionX: "110px", backgroundPositionY: "230px", backgroundRepeat: "no-repeat", border: "2px dashed gray", borderRadius: "30px", padding: "1rem 0.5rem 1rem 0.5rem"}}>
      <p className="text-[20px] font-large text-gray-500 uppercase tracking-wide" style={{ display: "flex", justifyContent: "center", width: "100%", marginLeft: "10px", marginBottom: "1.5rem", alignText: "center", fontWeight: "bold" }}>Nahraná Hláška</p>
        
      <audio ref={playerRef} src={audioPlayer.url} autoPlay preload="auto" controls style={{display: "flex", justifySelf: "center", width: "90%", margin: "auto 5%"}}>
        <source src={audioPlayer.url} type="audio/webm"/>
      </audio>
      <span style={{display: "flex", flexDirection: "row", alignItems: "center", position: "relative", width: "17%", height: "50px"}}>
          <p className="text-[15px] font-medium text-gray-500 uppercase tracking-wide" style={{ display: "inline-block", minWidth: "250px", marginLeft: "10px" }}>Pridať oneskorenie</p>
          <input value={waitBefore} onChange={e => processWaitBeforeChange(e.target.value)} name="waitBefore" step="1" type="number" style={{display: "inline-block", marginTop: "1rem", width: "75px", height: "50px", textAlign: "right"}}/>
          <span style={{position: "absolute", top: "22px",  right: "-275px", height: "50px", alignSelf: "center"}}>s</span>
      </span>   
      {/* <div style={{display: "flex", flexDirection: "row", justifyItems: "center", justifyContent: "center", height: "75px"}}>
          <button style={{width: "125px", height: "50px"}} onClick={handlePlay}>Play</button>
          <button style={{width: "125px", height: "50px"}} onClick={handlePause}>Pause</button>
          <button style={{width: "125px", height: "50px"}} onClick={handleStop}>Stop</button>
          <button style={{width: "125px", height: "50px"}} onClick={handleFocus}>Focus</button>
      </div> */}
      <form onSubmit={handleClip}>
        <p className="text-[15px] font-medium text-gray-500 uppercase tracking-wide" style={{ width: "100%", marginLeft: "10px", marginBottom: "0.5rem" }}>Získať výrez</p>
        <div style={{display: "flex", justifyContent: "space-between", flexDirection: "row", margin: "0 auto", width: "95%", height: "75px"}}>
          <span style={{display: "flex", flexDirection: "row", border: "3px solid black", justifyItems: "center", justifyContent: "center", height: "50px", borderRadius: "25px", backgroundColor: "grey"}}>
            <span style={{display: "inner-flex", alignItems: "center", position: "relative", width: "17%", height: "50px"}}>
              <input name="startInterval" step=".01" type="number" defaultValue="0.0" style={{width: "50px", height: "50px"}}/>
              <span style={{position: "absolute", top: "13px",  right: "-5px", height: "50px", alignSelf: "center"}}>s</span>
            </span>
           <span style={{margin: "0 25px 0 25px", alignSelf: "center"}}>
              <svg version="1.2" width="12.7mm" height="8.89mm" viewBox="0 0 1270 889" preserveAspectRatio="xMidYMid" fillRule="evenodd" strokeWidth="28.222" strokeLinejoin="round" xmlns="http://www.w3.org/2000/svg" xmlns:ooo="http://xml.openoffice.org/svg/export" xxmlns:xlink="http://www.w3.org/1999/xlink" xmlns:presentation="http://sun.com/xmlns/staroffice/presentation" xmlns:smil="http://www.w3.org/2001/SMIL20/" xmlns:anim="urn:oasis:names:tc:opendocument:xmlns:animation:1.0" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" xmlSpace="preserve">
                <defs className="ClipPathGroup">
                  <clipPath id="presentation_clip_path" clipPathUnits="userSpaceOnUse">
                  <rect x="0" y="0" width="1270" height="889"/>
                  </clipPath>
                  <clipPath id="presentation_clip_path_shrink" clipPathUnits="userSpaceOnUse">
                  <rect x="1" y="0" width="1268" height="888"/>
                  </clipPath>
                </defs>
                <defs className="TextShapeIndex">
                  <g ooo:slide="id1" ooo:id-list="id3"/>
                </defs>
                <defs className="EmbeddedBulletChars">
                  <g id="bullet-char-template-57356" transform="scale(0.00048828125,-0.00048828125)">
                  <path d="M 580,1141 L 1163,571 580,0 -4,571 580,1141 Z"/>
                  </g>
                  <g id="bullet-char-template-57354" transform="scale(0.00048828125,-0.00048828125)">
                  <path d="M 8,1128 L 1137,1128 1137,0 8,0 8,1128 Z"/>
                  </g>
                  <g id="bullet-char-template-10146" transform="scale(0.00048828125,-0.00048828125)">
                  <path d="M 174,0 L 602,739 174,1481 1456,739 174,0 Z M 1358,739 L 309,1346 659,739 1358,739 Z"/>
                  </g>
                  <g id="bullet-char-template-10132" transform="scale(0.00048828125,-0.00048828125)">
                  <path d="M 2015,739 L 1276,0 717,0 1260,543 174,543 174,936 1260,936 717,1481 1274,1481 2015,739 Z"/>
                  </g>
                  <g id="bullet-char-template-10007" transform="scale(0.00048828125,-0.00048828125)">
                  <path d="M 0,-2 C -7,14 -16,27 -25,37 L 356,567 C 262,823 215,952 215,954 215,979 228,992 255,992 264,992 276,990 289,987 310,991 331,999 354,1012 L 381,999 492,748 772,1049 836,1024 860,1049 C 881,1039 901,1025 922,1006 886,937 835,863 770,784 769,783 710,716 594,584 L 774,223 C 774,196 753,168 711,139 L 727,119 C 717,90 699,76 672,76 641,76 570,178 457,381 L 164,-76 C 142,-110 111,-127 72,-127 30,-127 9,-110 8,-76 1,-67 -2,-52 -2,-32 -2,-23 -1,-13 0,-2 Z"/>
                  </g>
                  <g id="bullet-char-template-10004" transform="scale(0.00048828125,-0.00048828125)">
                  <path d="M 285,-33 C 182,-33 111,30 74,156 52,228 41,333 41,471 41,549 55,616 82,672 116,743 169,778 240,778 293,778 328,747 346,684 L 369,508 C 377,444 397,411 428,410 L 1163,1116 C 1174,1127 1196,1133 1229,1133 1271,1133 1292,1118 1292,1087 L 1292,965 C 1292,929 1282,901 1262,881 L 442,47 C 390,-6 338,-33 285,-33 Z"/>
                  </g>
                  <g id="bullet-char-template-9679" transform="scale(0.00048828125,-0.00048828125)">
                  <path d="M 813,0 C 632,0 489,54 383,161 276,268 223,411 223,592 223,773 276,916 383,1023 489,1130 632,1184 813,1184 992,1184 1136,1130 1245,1023 1353,916 1407,772 1407,592 1407,412 1353,268 1245,161 1136,54 992,0 813,0 Z"/>
                  </g>
                  <g id="bullet-char-template-8226" transform="scale(0.00048828125,-0.00048828125)">
                  <path d="M 346,457 C 273,457 209,483 155,535 101,586 74,649 74,723 74,796 101,859 155,911 209,963 273,989 346,989 419,989 480,963 531,910 582,859 608,796 608,723 608,648 583,586 532,535 482,483 420,457 346,457 Z"/>
                  </g>
                  <g id="bullet-char-template-8211" transform="scale(0.00048828125,-0.00048828125)">
                  <path d="M -4,459 L 1135,459 1135,606 -4,606 -4,459 Z"/>
                  </g>
                  <g id="bullet-char-template-61548" transform="scale(0.00048828125,-0.00048828125)">
                  <path d="M 173,740 C 173,903 231,1043 346,1159 462,1274 601,1332 765,1332 928,1332 1067,1274 1183,1159 1299,1043 1357,903 1357,740 1357,577 1299,437 1183,322 1067,206 928,148 765,148 601,148 462,206 346,322 231,437 173,577 173,740 Z"/>
                  </g>
                </defs>
                <g>
                  <g id="id2" className="Master_Slide">
                  <g id="bg-id2" className="Background"/>
                  <g id="bo-id2" className="BackgroundObjects"/>
                  </g>
                </g>
                <g className="SlideGroup">
                  <g>
                  <g id="container-id1">
                    <g id="id1" className="Slide" clipPath="url(#presentation_clip_path)">
                    <g className="Page">
                      <g className="Group">
                      <g className="com.sun.star.drawing.ClosedBezierShape">
                        <g id="id3">
                        <rect className="BoundingBox" stroke="none" fill="none" x="-1" y="124" width="1273" height="613"/>
                        <path fill="rgb(255,51,51)" stroke="none" d="M 1270,430 C 1189,328 1107,226 1026,125 999,159 972,193 945,227 980,271 1015,315 1050,358 700,358 350,358 0,358 0,406 0,454 0,502 350,502 700,502 1050,502 1015,546 981,590 946,634 973,667 1000,701 1027,735 1108,633 1189,531 1270,430 Z "/>
                        </g>
                      </g>
                      </g>
                    </g>
                    </g>
                  </g>
                  </g>
                </g>
                </svg>
            </span>
            <span  style={{display: "inner-flex", alignItems: "center",  position: "relative", width: "17%", height: "50px"}}>
              <input style={{width: "50px", height: "50px"}} step=".01" name="endInterval" type="number" value={duration}
              onChange={e => setDuration(audioPlayer.blob, duration)}/>
              <span style={{position: "absolute", top: "13px", right: "-5px", height: "50px", alignSelf: "center"}}>s</span>
            </span>
          </span>
          <span style={{display: "table", width: "calc(83% - 250px)", margin: "0 auto"}}></span>
          <input type="submit" value="Orezať" style={{width: "175px", height: "50px", fontSize: "large", fontWeight: "bold", backgroundColor: secondaryButtonColor, borderRadius: "25px"}} />
        </div>
        
      </form>
      <p className="text-[15px] font-medium text-gray-500 uppercase tracking-wide" style={{ flex: "0 0 calc(100% - 70px)", marginLeft: "10px", marginBottom: "0.5rem" }}>Konverzia zvuku na text:</p>
      <textarea ref={textFromVideoTextareaRef} style={{width: "100%", height: "100px", border: "1px solid black", borderRadius: "25px", padding: "30px 30px 30px 30px"}} name="textFromVideo"  onChange={e => { 
        setTextAreaText(e.target.value); return e.target.value;
      }}>
      {textAreaText}
      </textarea>
      <div style={{display: "flex", justifyContent: "space-between"}}>
            <button
              onClick={onDelete}
              disabled={deleting}
              className="w-full flex items-center justify-center gap-1.5 text-[11px] text-gray-400 hover:text-red-500 transition-colors py-1 rounded-md hover:bg-red-50"
              aria-label="Odstrániť hlašku"
              style={{width: "225px", height: "50px", alignSelf: "center", margin: "1.5rem 8% 10px 25px"}}
            >
            {deleting
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <Trash2 className="h-3.5 w-3.5" />
            }
            Odstrániť
          </button>
        <Button style={{width: "55%", margin: "1.5rem 10px 10px 10px", color: "white", borderRadius: "25px", fontSize: "large", fontWeight: "bold", height: standardButtonHeight}} onClick={extractFromVideo}>
          {extracting
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <Pickaxe className="h-3.5 w-3.5" />
            }
        Extrahuj text z audia</Button>
        <Button style={{width: "15%", margin: "1.5rem 25px 10px 2%", color: "white", borderRadius: "25px", fontSize: "large", fontWeight: "bold", height: standardButtonHeight}} onClick={extendValueFromTextAreas}>
         <ArrowRight className="h-3.5 w-3.5" /> 
        Doplň</Button>
      </div>
    </div>
  );
}