clear all

Direc = ['..\Data\23-06-06 Eberto\'];
carp = 'Objeto\';


flag_roipoly = 1;


n_poses = 1;

% Camera and projector resolutions
m_imageWidth = 1280; %1024;        %1936   %1280 ;     %2048
m_imageHeight = 1024; %800;       %1464   %1024 ;     %1536
m_projectorWidth =  1280; %912;    %912    %1280;      %912
m_projectorHeight = 800; %1140;   %1140   %800;       %1140

% Fringe features: patterns period and shifts
FringePitch = 18; NStep = 18; NBits = 7;
nitext = NStep+NBits;


Fx = zeros(m_imageHeight,m_imageWidth,n_poses) ;
Fy = Fx;  images = Fx; MaskC = Fx; qFx = Fx; qFy = Fx;

gammaTh = 0.1;

if(flag_roipoly)
    figure(81)
    g = imagesc(zeros(2*[m_imageHeight m_imageWidth])); colormap gray
    g1 = drawpolygon();
%     g1 = drawcircle;

    Iaux = zeros(2*[m_imageHeight m_imageWidth]);
end



for i = 1:n_poses
    
    if(i<11), aux = ['0' num2str(i-1)]; else, aux = num2str(i-1); end

    % Deteccion de puntos - circuloF2_F3_2s
    Itex = imread([Direc, carp ,'pose_',aux,'\H\P',num2str(FringePitch),'_F',num2str(nitext),'.png']);
    images(:,:,i)= Itex;


    % Extraccion de fase
    fileEx = [Direc, carp ,'pose_',aux,'\V\P',num2str(FringePitch),'_F'];
    [Fx_aux, mask_h, texture_h, codeWord, ph,gmx] = UnwrapPhaseGrayCode(fileEx, FringePitch, NStep, NBits, [5 5],gammaTh);
    Fx(:,:,i) = Fx_aux;
    qFx(:,:,i) = gmx;

    fileEx = [Direc, carp ,'pose_',aux,'\H\P',num2str(FringePitch),'_F'];
    [Fy_aux, mask_v, texture_v, codeWord, ph,gmy] = UnwrapPhaseGrayCode(fileEx, FringePitch, NStep, NBits, [5 5],gammaTh);
    Fy(:,:,i) = Fy_aux;
    qFy(:,:,i) = gmy;


    if(flag_roipoly)
        figure(81), 
        Iaux(0.5*m_imageHeight:(1.5*m_imageHeight-1),0.5*m_imageWidth:(1.5*m_imageWidth-1)) = Itex;
        g.CData = Iaux;
        title(['Imagen ',num2str(i)])
        pause();
        mm = g1.createMask;
        MaskC(:,:,i) = mm(0.5*m_imageHeight:(1.5*m_imageHeight-1),0.5*m_imageWidth:(1.5*m_imageWidth-1));
%         MaskC(:,:,i) = rec;
    else
        MaskC(:,:,i) = mask_v.*mask_h.*(Itex>25);
    end


    figure(800),imagesc(Fx_aux.*MaskC(:,:,i)), title('Unwrapped H Phase - GrayCode');
    title(['Imagen ',num2str(i)]), drawnow

    figure(801),imagesc(Itex), title('captured image'); colormap gray
    title(['Imagen ',num2str(i)]), drawnow

end
%%
save([Direc,carp,carp(1:end-1),'_PhasesData.mat'],'Fx','Fy','qFx','qFy','images','MaskC')


%%

figure, imshow(images(:,:,1),[])
g1 = drawcircle;

hh = gca;
hh.Children(2).CData = images(:,:,3);
%%
Fx(:,:,27:end)       = [];
Fy(:,:,27:end)       = [];
qFx(:,:,27:end)      = [];
qFy(:,:,27:end)      = [];
images(:,:,27:end)   = [];
MaskC(:,:,27:end)    = [];



