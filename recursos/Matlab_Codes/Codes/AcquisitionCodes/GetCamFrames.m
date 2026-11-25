function Frames = GetCamFrames(vid,nFrames)
res = vid.VideoResolution;
Frames = uint8(zeros([res(2) res(1) nFrames]));
for i=1:nFrames
    I1=getsnapshot(vid);
    pause(0.010)
    Frames(:,:,i) = I1;
    %     disp(num2str(i))
    fprintf('.%i.',i)
end
fprintf('\n Imagenes capturadas \n')

end