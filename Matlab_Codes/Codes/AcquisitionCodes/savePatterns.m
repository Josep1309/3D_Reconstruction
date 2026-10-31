function savePatterns(Dire, nomb, patterns, nImaRef,secN)
%%
%
% nImaRef: La posicion en patterns de la ultima imagen de la secuencia
%
if ~isempty(nImaRef)
   patterns =  circshift(patterns,size(patterns,3)-nImaRef,3);
end

Nimags = size(patterns,3);
mkdir([Dire,'H'])

k=0;
for i = [0:secN(1)-1 (Nimags-secN(3)):Nimags-1]
    aux = num2str(k);
    if k<10
        aux= ['0' aux];
    end
    imwrite(patterns(:,:,i+1),[Dire,'H\',nomb,aux,'.png'],'png')
    k = k+1;
end

mkdir([Dire,'V'])
for i = secN(2):Nimags-1
    aux = num2str(i-secN(2));
    if (i-secN(2))<10
        aux= ['0' aux];
    end
    imwrite(patterns(:,:,i+1),[Dire,'V\',nomb,aux,'.png'],'png')
end

end