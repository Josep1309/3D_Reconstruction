function  [Fasesxa,Fasesya,Maskx2,Masky2] = CleanPhase(Fasesx,Fasesy,Mask,op)
%% 
%
% Estima un polinomio de fase de grado 5 para mapas de fases en dos
% direcciones. 
% input:
%  Fasesx,Fasesy : Matrices de MxNxP
%  Mask: Mascara binaria para escoger los pixeles utilizados para realizar
%  el ajuste polinomial.
% op: es una variables binaria para controlar la visualización de los
% errores residuales
%
grado =5;
[Fasesxa,FX] =  PhaseAdj5(Fasesx,Mask,grado,1,[],5);
[Fasesya,FY] =  PhaseAdj5(Fasesy,Mask,grado,1,[],5);
if(op==1)
    for i=1:size(FX,3)
        figure(700+2*i)  , imagesc(FX(:,:,i)), title(['Error Ajuste imagen ',num2str(i),' Franjas V']), colorbar, caxis([-0.08 0.08]), colormap gray; drawnow
        figure(700+2*i+1), imagesc(FY(:,:,i)), title(['Error Ajuste imagen ',num2str(i),' Franjas H']), colorbar, caxis([-0.08 0.08]), colormap gray; drawnow
        
    end
end
Maskx2 = Mask.*(FX>-0.3 & FX<0.3);
Masky2 = Mask.*(FY>-0.3 & FY<0.3);

end